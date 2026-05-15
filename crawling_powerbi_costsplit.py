import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

# --- Configuration ---
URL = "https://app.powerbi.com/view?r=eyJrIjoiNWM3ZmI0OTYtNzdmYi00ZjhjLThiNWYtNTE3MjdkY2FlNjFhIiwidCI6IjA1YzVjOTYzLWM4MzktNGM5ZS1iNWMxLWI1MWIzNzk5YWMzNyJ9"
OUTPUT_FILE = "WorkSafeBC_Costs_Long_Format.csv"

def toggle_cu_state(driver, cu_title, target_state):
    """Switch selection state using js. Fixes apostrophe errors."""
    escaped_title = cu_title.replace("'", "\\'")
    script = f"""
        var target = document.querySelector('div.slicerItemContainer[title="{escaped_title}"]');
        if (target) {{
            var currentState = target.getAttribute('aria-selected');
            if (currentState !== "{target_state}") {{
                var clickEvent = new MouseEvent('click', {{ view: window, bubbles: true, cancelable: true }});
                target.dispatchEvent(clickEvent);
                return "Updated";
            }}
            return "Found but already in target state";
        }}
        return "NotFound";
    """
    return driver.execute_script(script)

def scrape_costs_table(driver, cu_name):
    """Extracts data strictly from the 'Show as a table' pop-up focus view."""
    all_rows = []
    
    # 1. Wait for the specific detail-visual grid to render (ignoring background tables)
    wait = WebDriverWait(driver, 10)
    grid = wait.until(EC.presence_of_element_located((By.XPATH, "//detail-visual//div[contains(@class, 'interactive-grid')]")))
    
    # 2. Scope all our searches to inside this specific 'grid'
    header_elements = grid.find_elements(By.XPATH, ".//div[@role='columnheader']//div[contains(@class, 'pivotTableCellWrap')]")
    headers = [h.text.strip() for h in header_elements if h.text.strip() and h.text.strip() != 'Year']
    
    # Fallback headers just in case they don't render text immediately
    if len(headers) < 2:
        headers = ['Claim Costs Paid (Other Years)', 'Claim Costs Paid (Year of Injury)']

    # Extract rows ONLY from the pop-up grid
    row_elements = grid.find_elements(By.XPATH, ".//div[@role='row']")
    
    for row in row_elements:
        # Check if it's a data row by looking for a rowheader (Year)
        year_el = row.find_elements(By.XPATH, ".//div[@role='rowheader']")
        if not year_el:
            continue
        
        year = year_el[0].text.strip()
        
        # Make sure the year is valid (filters out potential blank/aggregate rows)
        if not (year.isdigit() and 2014 <= int(year) <= 2026):
            continue
            
        cells = row.find_elements(By.XPATH, ".//div[@role='gridcell']")
        
        if len(cells) == len(headers):
            for i, cell in enumerate(cells):
                val = cell.text.replace(',', '').replace('$', '').strip()
                all_rows.append({
                    'CU': cu_name,
                    'Metric': headers[i],
                    'Year': year,
                    'Value': val
                })
                
    return pd.DataFrame(all_rows).drop_duplicates()

def run_production_scraper():
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 15)
    actions = ActionChains(driver)

    try:
        driver.get(URL)
        time.sleep(5)
        
        # Navigate to Costs instead of CU Profile
        svg_path_script = """
        var textDiv = document.evaluate("//div[contains(text(), 'Costs')]", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
        if (textDiv) {
            var container = textDiv.closest('.pageNavigator');
            var path = container.querySelector('path');
            if (path) {
                path.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                path.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                path.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                return "SVG Path Clicked";
            }
        }
        return "Path not found";
        """
        driver.execute_script(svg_path_script)
        time.sleep(5)

        # Open Industry Classification Unit slicer
        slicer = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@aria-label='Industry Classification Unit']")))
        driver.execute_script("arguments[0].click();", slicer)
        time.sleep(3)

        # Resume previous progress if CSV exists
        if os.path.isfile(OUTPUT_FILE):
            existing_df = pd.read_csv(OUTPUT_FILE)
            processed_cus = set(existing_df['CU'].unique())
            print(f"Resuming. {len(processed_cus)} units already in CSV.")
        else:
            processed_cus = set()

        previous_cu = None
        consecutive_no_new = 0

        while consecutive_no_new < 50:
            visible_elements = driver.find_elements(By.CLASS_NAME, "slicerItemContainer")
            
            # Look for the first unprocessed CU in the currently visible list
            target_cu = None
            for el in visible_elements:
                title = el.get_attribute("title")
                if title and title[0].isdigit() and title not in processed_cus:
                    target_cu = title
                    break

            # If all visible CUs are already processed, scroll down to reveal more
            if not target_cu:
                consecutive_no_new += 1
                if visible_elements:
                    driver.execute_script("arguments[0].scrollIntoView(true);", visible_elements[-1])
                time.sleep(1) # Fast sleep (1s) to rapidly catch up to the frontier
                continue
            
            # We found a new CU! Reset the scroll timeout counter
            consecutive_no_new = 0 

            print(f"--- Processing: {target_cu} ---")
            
            # Toggle Slicer
            if previous_cu:
                toggle_cu_state(driver, previous_cu, "false")
            
            toggle_result = toggle_cu_state(driver, target_cu, "true")
            
            # Safety check: if the scroll jittered and it lost the element, loop and try finding it again
            if toggle_result == "NotFound":
                print(f"Warning: {target_cu} temporarily lost from DOM. Retrying...")
                continue
                
            time.sleep(3) # Wait for chart to update
            
            # 1. Locate and right-click the specific chart body
            chart_container = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//visual-container[.//h3[contains(text(), 'Claim Costs Paid ($)')]]")
            ))
            chart_body = chart_container.find_element(By.CLASS_NAME, "vcBody")
            actions.context_click(chart_body).perform()
            time.sleep(1.5)

            # 2. Left-click 'Show as a table'
            show_table_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[@title='Show as a table']")
            ))
            driver.execute_script("arguments[0].click();", show_table_btn)
            time.sleep(3)
            
            # 3. Scrape the table (using the specific pop-up scoped function)
            df_long = scrape_costs_table(driver, target_cu)
            
            # Save to CSV
            file_exists = os.path.isfile(OUTPUT_FILE)
            df_long.to_csv(OUTPUT_FILE, mode='a', index=False, header=not file_exists)
            
            # 4. Return to report
            back_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Back to report')]")))
            driver.execute_script("arguments[0].click();", back_btn)
            time.sleep(2)
            
            # 5. Re-open the slicer for the next iteration
            slicer = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@aria-label='Industry Classification Unit']")))
            driver.execute_script("arguments[0].click();", slicer)
            time.sleep(2)
            
            # Mark as done
            processed_cus.add(target_cu)
            previous_cu = target_cu
            print(f"Success. Progress: {len(processed_cus)} units.")

    except Exception as e:
        print(f"Fatal Error: {e}")
    finally:
        driver.quit()

run_production_scraper()