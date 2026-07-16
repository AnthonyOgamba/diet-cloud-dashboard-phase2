# Nutritional Insights Frontend

A static HTML, CSS, and JavaScript dashboard for the Diet Analysis Azure Function. The dashboard retrieves live nutritional data from the deployed Azure Function and uses the response to populate its metadata, filters, and visualizations.

## Live Deployment

- **Dashboard:** https://green-forest-0c37b491e.7.azurestaticapps.net
- **Azure Function:** https://anthony-diet-dashboard-99241.azurewebsites.net/api/dietanalysisfunction

## Visualizations

The dashboard contains four data visualizations:

- Bar chart showing average protein by diet type
- Scatter plot comparing average carbohydrates and protein
- HTML/CSS heatmap comparing protein, carbohydrates, and fat
- Pie chart showing the distribution of diet records

## Run Locally

The frontend is currently configured to use the deployed Azure Function, so the local Function does not need to be running.

Serve the frontend from a terminal:

```powershell
cd C:\DietCloudPhase2\frontend
python -m http.server 5500