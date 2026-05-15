import pandas as pd
import re
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- Configuration ---
URL = "https://app.powerbi.com/view?r=eyJrIjoiNWM3ZmI0OTYtNzdmYi00ZjhjLThiNWYtNTE3MjdkY2FlNjFhIiwidCI6IjA1YzVjOTYzLWM4MzktNGM5ZS1iNWMxLWI1MWIzNzk5YWMzNyJ9"
OUTPUT_FILE = "WorkSafeBC_Project_Long_Format_Test.csv"

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

def scrape_table_to_long(driver, cu_name):
    """Captures 45 rows, and filters out fake years, reset table scroll."""
    grid = driver.find_element(By.CLASS_NAME, "interactive-grid")
    scroll_area = driver.find_element(By.CLASS_NAME, "mid-viewport")
    
    all_rows = []
    # Two snapshots (0px and 450px) to capture the full 45-row vertical table
    for step in range(2):
        html = grid.get_attribute('outerHTML')
        
        # Extract years from the header, ensuring they are valid and in the expected range
        years = sorted([
            y for y in set(re.findall(r'>(\d{4})</div>', html)) 
            if 2014 <= int(y) <= 2026
        ])
        
        labels = [l.strip() for l in re.findall(r'role="rowheader".*?>(.*?)</div>', html) if l.strip()]
        values = [v.replace('&nbsp;', '').strip() for v in re.findall(r'role="gridcell".*?>(.*?)</div>', html)]
        
        num_cols = len(years)
        if num_cols > 0:
            for i, label in enumerate(labels):
                row_vals = values[i*num_cols : (i+1)*num_cols]
                if len(row_vals) == num_cols:
                    for yr, val in zip(years, row_vals):
                        all_rows.append({
                            'Classification_Unit': cu_name,
                            'Metric': label,
                            'Year': yr,
                            'Value': val.replace(',', '').replace('%', '')
                        })
        
        # Scroll down for the second half of the metrics
        driver.execute_script("arguments[0].scrollTop += 450;", scroll_area)
        time.sleep(3)

    # Reset the table scroll to the top for the new CU
    driver.execute_script("arguments[0].scrollTop = 0;", scroll_area)
    time.sleep(3) # Allow the top rows to render

        
    return pd.DataFrame(all_rows).drop_duplicates()

def run_production_scraper():
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)

    try:
        driver.get(URL)
        time.sleep(5)
        
        # Navigate to CU Profile
        # profile_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'CU Profile')]")))
        # driver.execute_script("arguments[0].click();", profile_btn)
        # replaced by a SVG click (Scalable Vector Graphics)

        svg_path_script = """
        var textDiv = document.evaluate("//div[contains(text(), 'CU Profile')]", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
        var container = textDiv.closest('.pageNavigator');
        var path = container.querySelector('path');
        if (path) {
            path.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
            path.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
            path.dispatchEvent(new MouseEvent('click', {bubbles: true}));
            return "SVG Path Clicked";
        }
        return "Path not found";
        """
        driver.execute_script(svg_path_script)

        time.sleep(5)

        # Open Industry Classification Unit slicer
        slicer = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@aria-label='Industry Classification Unit']")))
        driver.execute_script("arguments[0].click();", slicer)
        time.sleep(3)

        # Resume previous progress if CSV exists, otherwise start fresh
        if os.path.isfile(OUTPUT_FILE):
            existing_df = pd.read_csv(OUTPUT_FILE)
            processed_cus = set(existing_df['Classification_Unit'].unique())
            print(f"Resuming. {len(processed_cus)} units already in CSV.")
        else:
            processed_cus = set()

        previous_cu = None
        consecutive_no_new = 0

        while consecutive_no_new < 50:
            visible_elements = driver.find_elements(By.CLASS_NAME, "slicerItemContainer")
            new_cus_in_batch = []

            for el in visible_elements:
                title = el.get_attribute("title")
                if title and title[0].isdigit() and title not in processed_cus:
                    new_cus_in_batch.append(title)

            if not new_cus_in_batch:
                consecutive_no_new += 1
                if visible_elements:
                    driver.execute_script("arguments[0].scrollIntoView(true);", visible_elements[-1])
                time.sleep(3)
                continue
            
            consecutive_no_new = 0 

            for current_cu in new_cus_in_batch:
                print(f"--- Processing: {current_cu} ---")
                
                if previous_cu:
                    toggle_cu_state(driver, previous_cu, "false")
                toggle_cu_state(driver, current_cu, "true")
                
                time.sleep(3)
                
                df_long = scrape_table_to_long(driver, current_cu)
                
                file_exists = os.path.isfile(OUTPUT_FILE)
                df_long.to_csv(OUTPUT_FILE, mode='a', index=False, header=not file_exists)
                
                processed_cus.add(current_cu)
                previous_cu = current_cu
                print(f"Success. Progress: {len(processed_cus)} units.")

    except Exception as e:
        print(f"Fatal Error: {e}")
    finally:
        driver.quit()

run_production_scraper()