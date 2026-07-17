# Member 2 – Azure Backend Implementation

## Team Member
Krima Patel

## Responsibilities Completed

- Created an Azure Storage Account.
- Created the `datasets` blob container.
- Uploaded `cleaned_diets_dataset.csv`.
- Created the Azure Function App `krima-diet-function`.
- Developed an HTTP-triggered Python Azure Function.
- Connected the Azure Function to Azure Blob Storage.
- Loaded the CSV dataset using pandas.
- Generated summary statistics, diet distribution, average nutrition data, and chart-ready data.
- Tested the Azure Function successfully in the local environment.
- Deployed the backend project to Azure.

## Azure Resources

- Storage Account: `krimadietstorage`
- Blob Container: `datasets`
- Dataset: `cleaned_diets_dataset.csv`
- Function App: `krima-diet-function`
- Function Route: `DietAnalysisFunction`

## Testing Result

The Azure Function worked successfully during local testing and returned the expected JSON response.

The deployment to Azure completed successfully. However, the live Azure endpoint returned a 404 error because the function was not indexed correctly in the deployed Function App. The local implementation and deployment process were completed and documented.

## Security Note

The Azure Storage connection string is stored in environment settings and is not included in the GitHub repository.