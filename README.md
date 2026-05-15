# WorkSafeBC: Modeling Industry-Specific Claim Costs

Course: Risk 421 Spring2026, Simon Fraser University

Team Members: Stuart Siu, Peter Bui, and Anna Lukanov

## Objective
Developed a predictive statistical model using WorkSafeBC claims data to analyze and forecast industry-specific claim cost trends. 

The project utilizes hierarchical Generalized Linear Mixed Models (GLMMs) to evaluate **payroll-adjusted claim costs** (pure premium), **isolating** the underlying injury-year **time trend** while accounting for **structural heterogeneity** across British Columbia’s labor market subsectors.

## The Business Problem
In workers' compensation and **property & casualty** (P&C) insurance, evaluating the true risk profile of an industry is challenging due to the noise created by **macroeconomic factors** (like wage inflation or post-2020 economic shocks). 

<img width="50%" alt="image" src="https://github.com/user-attachments/assets/0e03b347-3d3b-4029-94ef-62c036a14395" />


Furthermore, aggregate claim costs obscure the differing behaviors of newly reported incidents versus the long-tail development of existing claims. 
To set accurate insurance rates and maintain adequate reserves, actuaries must detrend external economic impacts and properly align risk exposure to understand the inherent, structural risk of specific occupational classifications.

## Statistical Methodology
The analysis was conducted using advanced predictive analytics and loss reserving frameworks:

- **Data Engineering:** Automated the extraction of granular Industry Health & Safety data from WorkSafeBC interactive dashboards using **Python (Selenium)**, structuring it for longitudinal analysis.
- **Bifurcated Modeling:** Separated total claim costs into **"injury-year" (current)** and **"prior-year" (runoff)** components to accurately reflect the development of long-tail claims.
- **Hierarchical GLMMs:** Built Generalized Linear Mixed Models (estimated via maximum likelihood and Laplace approximation) to account for the nested structure of Classification Units (CUs) within industry subsectors.

  <img width="50%" alt="image" src="https://github.com/user-attachments/assets/6c1e3727-a895-41a1-8051-8b44d66ed8e6" />

- **Exposure Alignment:** Addressed the mismatch between current economic activity and long-tail claim emergence by implementing **rolling-average** and lagged payroll exposure metrics.

  <img width="50%" alt="image" src="https://github.com/user-attachments/assets/60803658-d534-4ad3-9132-a1443d9d2072" />
  
- **Feature Selection:** Utilized an **iterative backward stepwise GLM** to isolate the most statistically significant cost drivers (e.g., time-loss claims, return-to-work rates, average days lost).

  <img width="60%" alt="image" src="https://github.com/user-attachments/assets/0a1bd781-b6c9-4e1b-9665-c7be97046e8a" />


## Tech Stack
- Mathematics: Generalized Linear Mixed Models (GLMM), **Tweedie Distributions**, **Predictive Analytics**, and **Loss Reserving**.
- Languages & Tools: **R** (lme4, glmmTMB, stats), **Python** (Selenium for web scraping), Excel.

## Key Empirical Insights
Based on a **train-test split** (training on 2015-2022, testing on 2023-2024), the bifurcated GLMM approach yielded several critical insights into occupational risk:

### The Frequency vs. Severity Divide: 
Across multiple subsectors, immediate injury-year costs are heavily driven by **raw claim frequency** (time-loss claims). However, prior-year runoff costs are overwhelmingly driven by **claim severity and duration**. Claim frequency statistically fails to predict long-tail runoff costs, indicating that day-one risks and long-tail risks require entirely different **prevention** and **reserving** strategies.

<img width="534" height="212" alt="image" src="https://github.com/user-attachments/assets/5c44fd77-6ecb-4748-b676-42144775deb2" />

### Predictive Exposure Alignment: 
Empirical analysis revealed that utilizing a one-year lagged payroll exposure specification, rather than current-year payroll, provided the most accurate fit for **prior-year claim development**. Aligning exposure closer to claim realization drastically reduced the **out-of-sample prediction error**.

<img width="50%" alt="image" src="https://github.com/user-attachments/assets/a925ef5f-0cc3-4ded-a3b1-9cf5905de577" />



### Isolating Structural Risk (Heavy Construction): 
By **isolating structural variance** at the CU level, the model quantified a stark risk divide between manual trades (e.g., ironworkers, who face severe long-term recovery costs) and mechanized operations (e.g., tunnel driving). Furthermore, the 10-year baseline approach successfully stripped out **wage inflation distortions** caused by recent provincial mega-projects.

<img width="50%" alt="hvyconst_cu" src="https://github.com/user-attachments/assets/b2ea41bf-4851-4dd6-b140-1f27eb62e36d" />

### Embedded Occupational Hazards (Public Administration): 
Variables such as "Acts of Violence" initially appeared as highly significant cost drivers. However, introducing CU-level **random effects** completely absorbed this significance. This mathematically demonstrated that violent exposures are not independent variables, but rather inherent structural risks firmly embedded within the Law Enforcement classification.

<img width="50%" alt="pbadmin_cu" src="https://github.com/user-attachments/assets/fb75fa71-a663-4eef-9a46-555db9e6f029" />

