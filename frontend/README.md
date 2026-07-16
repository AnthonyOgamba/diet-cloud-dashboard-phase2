# Nutritional Insights frontend

Static HTML, CSS, and JavaScript dashboard for the Diet Analysis Azure Function. The dashboard uses only live Function response values for its metadata and visualizations.

## Visualizations

- Average protein by diet type bar chart
- Average carbohydrates vs. protein scatter plot
- HTML/CSS protein, carbohydrate, and fat heatmap
- Diet record distribution pie chart

## Run locally

Start the Azure Function backend:

```powershell
cd C:\DietCloudPhase2\backend
func start --cors http://localhost:5500
```

In a second terminal, serve the frontend:

```powershell
cd C:\DietCloudPhase2\frontend
python -m http.server 5500
```

Open `http://localhost:5500` in a browser. Do not open `index.html` with a `file://` URL.

The API endpoint is defined once near the top of `app.js`:

```javascript
const API_URL =
    "https://anthony-diet-dashboard-99241.azurewebsites.net/api/dietanalysisfunction";;
```

Replace this value with the deployed Azure Function URL for cloud deployment.

## CORS

For local development, the `--cors http://localhost:5500` argument above allows only the frontend's exact local origin. If the Function was already started with plain `func start`, stop it and restart it with that argument. In Azure, allow the deployed Static Web Apps origin. Do not expose connection strings, storage keys, Function secrets, or `local.settings.json` in frontend files.

## Interactions and limitations

The diet dropdown and Enter-key search request the selected diet from the Function. **Get Nutritional Insights** refreshes the current filter. **Get Recipes** reports that no recipe endpoint exists. **Get Clusters** explains and scrolls to the heatmap. Pagination updates only its visible UI state because the backend does not expose paginated records.
