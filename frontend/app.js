"use strict";

// Deployed Azure Function endpoint used by the dashboard.


const API_URL =
    "https://anthony-diet-dashboard-99241.azurewebsites.net/api/dietanalysisfunction";

const VALID_DIETS = ["all", "dash", "keto", "mediterranean", "paleo", "vegan"];
const PIE_COLORS = ["#4164E8", "#289865", "#7B35E8", "#F0A43C", "#E35572", "#25A7B8"];

let barChart = null;
let scatterChart = null;
let pieChart = null;
let requestInProgress = false;
let currentPage = 1;
const elements = {};

function buildApiUrl() {
    const url = new URL(API_URL);
    if (elements.dietFilter.value !== "all") {
        url.searchParams.set("diet", elements.dietFilter.value);
    }
    return url.toString();
}

async function fetchDashboardData(successMessage = "Nutritional insights updated successfully.") {
    if (requestInProgress) return;
    setLoadingState(true);

    try {
        const response = await fetch(buildApiUrl(), { headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error(`The Azure Function returned HTTP ${response.status}.`);

        let data;
        try {
            data = await response.json();
        } catch (error) {
            throw new Error("The Azure Function returned invalid JSON.", { cause: error });
        }

        if (data?.error) throw new Error(`Backend error: ${data.error}`);
        validateResponse(data);
        updateMetadata(data);
        renderBarChart(data.charts.bar_chart);
        renderScatterChart(data.average_nutrition);
        renderHeatmap(data.average_nutrition);
        renderPieChart(data.charts.pie_chart);
        showStatus(successMessage, "success");
    } catch (error) {
        console.error("Unable to retrieve dashboard data:", error);
        showStatus(
            `The dashboard could not connect to the Azure Function. It may not be running. Expected Azure Function endpoint: ${API_URL}. ${error.message}`,
            "error"
        );
    } finally {
        setLoadingState(false);
    }
}

function validateResponse(data) {
    if (!data || typeof data !== "object") throw new Error("The response body is missing.");
    if (!data.summary || !data.metadata || !data.average_nutrition || !data.charts) {
        throw new Error("The response is missing required dashboard fields.");
    }

    validateSeries(data.charts.bar_chart, ["values"], "bar chart");
    validateSeries(data.charts.pie_chart, ["values"], "pie chart");
    validateSeries(data.average_nutrition, ["protein", "carbs", "fat"], "nutrition");
}

function validateSeries(series, valueKeys, name) {
    if (!series || !Array.isArray(series.labels)) throw new Error(`Missing ${name} labels.`);
    valueKeys.forEach(key => {
        if (!Array.isArray(series[key]) || series[key].length !== series.labels.length) {
            throw new Error(`Invalid ${name} ${key} values.`);
        }
    });
}

function updateMetadata(data) {
    elements.totalRecords.textContent = formatNumber(data.summary.total_records, 0);
    elements.averageProtein.textContent = formatGrams(data.summary.avg_protein_overall);
    elements.averageCarbs.textContent = formatGrams(data.summary.avg_carbs_overall);
    elements.executionTime.textContent = `${formatNumber(data.metadata.execution_time_seconds, 3)} s`;
    elements.datasetName.textContent = data.metadata.blob || "Not provided";
    elements.datasetName.title = data.metadata.blob || "";
}

function renderBarChart(data) {
    barChart?.destroy();
    barChart = new Chart(document.getElementById("bar-chart"), {
        type: "bar",
        data: {
            labels: data.labels.map(formatDietName),
            datasets: [{
                label: "Average Protein (g)",
                data: data.values,
                backgroundColor: "rgba(65, 100, 232, 0.82)",
                borderColor: "#4164E8",
                borderWidth: 1,
                borderRadius: 5
            }]
        },
        options: axisChartOptions("Diet type", "Average protein (g)")
    });
}

function renderScatterChart(data) {
    const points = data.labels.map((diet, index) => ({
        x: Number(data.carbs[index]),
        y: Number(data.protein[index]),
        diet: formatDietName(diet)
    }));

    scatterChart?.destroy();
    scatterChart = new Chart(document.getElementById("scatter-chart"), {
        type: "scatter",
        data: {
            datasets: [{
                label: "Diet type",
                data: points,
                backgroundColor: "rgba(40, 152, 101, 0.82)",
                borderColor: "#1D754D",
                pointRadius: 7,
                pointHoverRadius: 9
            }]
        },
        options: {
            ...axisChartOptions("Average carbohydrates (g)", "Average protein (g)"),
            plugins: {
                legend: { display: true, position: "bottom" },
                tooltip: {
                    callbacks: {
                        label(context) {
                            const point = context.raw;
                            return [`Diet: ${point.diet}`, `Carbohydrates: ${formatNumber(point.x, 2)} g`, `Protein: ${formatNumber(point.y, 2)} g`];
                        }
                    }
                }
            }
        }
    });
}

function renderHeatmap(data) {
    const nutrients = [
        { label: "Protein", values: data.protein },
        { label: "Carbs", values: data.carbs },
        { label: "Fat", values: data.fat }
    ];
    const allValues = nutrients.flatMap(nutrient => nutrient.values.map(Number)).filter(Number.isFinite);
    const maximum = Math.max(...allValues, 1);

    const table = document.createElement("table");
    table.className = "heatmap-table";
    table.innerHTML = `<thead><tr><th scope="col">Diet type</th>${nutrients.map(item => `<th scope="col">${item.label}</th>`).join("")}</tr></thead>`;
    const body = document.createElement("tbody");

    data.labels.forEach((diet, rowIndex) => {
        const row = document.createElement("tr");
        const label = document.createElement("th");
        label.scope = "row";
        label.className = "diet-label";
        label.textContent = formatDietName(diet);
        row.appendChild(label);

        nutrients.forEach(nutrient => {
            const value = Number(nutrient.values[rowIndex]);
            const intensity = Number.isFinite(value) ? value / maximum : 0;
            const cell = document.createElement("td");
            cell.textContent = Number.isFinite(value) ? formatNumber(value, 1) : "—";
            cell.style.backgroundColor = `rgba(65, 100, 232, ${0.12 + intensity * 0.78})`;
            cell.style.color = intensity > 0.55 ? "#FFFFFF" : "#172554";
            cell.title = `${formatDietName(diet)} ${nutrient.label}: ${formatNumber(value, 2)} g`;
            row.appendChild(cell);
        });
        body.appendChild(row);
    });

    table.appendChild(body);
    elements.heatmap.replaceChildren(table);
}

function renderPieChart(data) {
    pieChart?.destroy();
    pieChart = new Chart(document.getElementById("pie-chart"), {
        type: "pie",
        data: {
            labels: data.labels.map(formatDietName),
            datasets: [{
                label: "Records",
                data: data.values,
                backgroundColor: data.labels.map((_, index) => PIE_COLORS[index % PIE_COLORS.length]),
                borderColor: "#FFFFFF",
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, position: "bottom", labels: { boxWidth: 11, padding: 10 } },
                tooltip: { callbacks: { label: context => `${context.label}: ${formatNumber(context.parsed, 0)} records` } }
            }
        }
    });
}

function axisChartOptions(xTitle, yTitle) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: true, position: "bottom" } },
        scales: {
            x: { title: { display: true, text: xTitle }, grid: { display: false } },
            y: { beginAtZero: true, title: { display: true, text: yTitle } }
        }
    };
}

function handleSearch(event) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const query = elements.dietSearch.value.trim().toLowerCase();
    const normalized = query === "all diet types" ? "all" : query;

    if (!VALID_DIETS.includes(normalized)) {
        showStatus("Enter a valid diet type: DASH, Keto, Mediterranean, Paleo, Vegan, or All Diet Types.", "info");
        return;
    }

    elements.dietFilter.value = normalized;
    elements.dietSearch.value = "";
    fetchDashboardData(`${formatDietName(normalized)} results loaded successfully.`);
}

function setLoadingState(isLoading) {
    requestInProgress = isLoading;
    elements.insightsButton.disabled = isLoading;
    elements.dietFilter.disabled = isLoading;
    elements.insightsButton.textContent = isLoading ? "Loading..." : "Get Nutritional Insights";
    if (isLoading) showStatus("Loading nutritional insights…", "");
}

function showStatus(message, type = "") {
    elements.statusMessage.textContent = message;
    elements.statusMessage.className = `status-message${type ? ` ${type}` : ""}`;
}

function changePage(page) {
    currentPage = Math.min(2, Math.max(1, page));
    elements.pageButtons.forEach(button => {
        const active = Number(button.dataset.page) === currentPage;
        button.classList.toggle("active", active);
        if (active) button.setAttribute("aria-current", "page");
        else button.removeAttribute("aria-current");
    });
    elements.previousPage.disabled = currentPage === 1;
    elements.nextPage.disabled = currentPage === 2;
    showStatus(`Page ${currentPage} selected. Pagination is a UI demonstration; the API does not return paginated records.`, "info");
}

function formatDietName(value) {
    if (String(value).toLowerCase() === "all") return "All Diet Types";
    const name = String(value).replace(/[_-]/g, " ").replace(/\b\w/g, letter => letter.toUpperCase());
    return name.toLowerCase() === "dash" ? "DASH" : name;
}

function formatNumber(value, maximumFractionDigits) {
    const number = Number(value);
    return Number.isFinite(number) ? new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(number) : "—";
}

function formatGrams(value) {
    const number = formatNumber(value, 2);
    return number === "—" ? number : `${number} g`;
}

function cacheElements() {
    Object.assign(elements, {
        totalRecords: document.getElementById("total-records"),
        averageProtein: document.getElementById("average-protein"),
        averageCarbs: document.getElementById("average-carbs"),
        executionTime: document.getElementById("execution-time"),
        datasetName: document.getElementById("dataset-name"),
        heatmap: document.getElementById("heatmap"),
        dietSearch: document.getElementById("diet-search"),
        dietFilter: document.getElementById("diet-filter"),
        insightsButton: document.getElementById("insights-button"),
        recipesButton: document.getElementById("recipes-button"),
        clustersButton: document.getElementById("clusters-button"),
        statusMessage: document.getElementById("status-message"),
        previousPage: document.getElementById("previous-page"),
        nextPage: document.getElementById("next-page"),
        pageButtons: [...document.querySelectorAll(".page-button")]
    });
}

document.addEventListener("DOMContentLoaded", () => {
    cacheElements();
    elements.dietFilter.addEventListener("change", () => fetchDashboardData(`${formatDietName(elements.dietFilter.value)} results loaded successfully.`));
    elements.dietSearch.addEventListener("keydown", handleSearch);
    elements.insightsButton.addEventListener("click", () => fetchDashboardData());
    elements.recipesButton.addEventListener("click", () => showStatus("Recipe endpoint is not available yet.", "info"));
    elements.clustersButton.addEventListener("click", () => {
        document.getElementById("heatmap-card").scrollIntoView({ behavior: "smooth", block: "center" });
        showStatus("The heatmap represents nutritional clusters through relative macronutrient intensity by diet type.", "info");
    });
    elements.previousPage.addEventListener("click", () => changePage(currentPage - 1));
    elements.nextPage.addEventListener("click", () => changePage(currentPage + 1));
    elements.pageButtons.forEach(button => button.addEventListener("click", () => changePage(Number(button.dataset.page))));
    changePage(1);
    fetchDashboardData();
});
