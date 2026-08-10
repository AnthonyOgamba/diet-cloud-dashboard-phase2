"use strict";


/* =========================================================
   AZURE API ENDPOINTS
========================================================= */

const DASHBOARD_API_URL =
    "https://anthony-diet-dashboard-99241.azurewebsites.net/api/dietanalysisfunction";

const RECIPES_API_URL =
    "https://anthony-diet-dashboard-99241.azurewebsites.net/api/recipes";


const VALID_DIETS = [
    "all",
    "dash",
    "keto",
    "mediterranean",
    "paleo",
    "vegan"
];


const PIE_COLORS = [
    "#4164E8",
    "#289865",
    "#7B35E8",
    "#F0A43C",
    "#E35572",
    "#25A7B8"
];


let barChart = null;
let scatterChart = null;
let pieChart = null;

let requestInProgress = false;

let currentPage = 1;
let totalPages = 1;
let pageSize = 5;

let dashboardInitialized = false;

const elements = {};


/* =========================================================
   DASHBOARD API URL
========================================================= */

function buildDashboardApiUrl() {
    const url =
        new URL(
            DASHBOARD_API_URL
        );

    if (
        elements.dietFilter.value !== "all"
    ) {
        url.searchParams.set(
            "diet",
            elements.dietFilter.value
        );
    }

    return url.toString();
}


/* =========================================================
   RECIPE API URL
========================================================= */

function buildRecipeApiUrl(page = 1) {
    const url =
        new URL(
            RECIPES_API_URL
        );

    const diet =
        elements.dietFilter.value;

    const keyword =
        elements.dietSearch.value.trim();

    if (diet !== "all") {
        url.searchParams.set(
            "diet",
            diet
        );
    }

    if (keyword) {
        url.searchParams.set(
            "q",
            keyword
        );
    }

    url.searchParams.set(
        "page",
        String(page)
    );

    url.searchParams.set(
        "pageSize",
        String(pageSize)
    );

    return url.toString();
}


/* =========================================================
   FETCH DASHBOARD DATA
========================================================= */

async function fetchDashboardData(
    successMessage =
        "Nutritional insights updated successfully."
) {
    if (requestInProgress) {
        return;
    }

    setLoadingState(true);

    try {
        const response = await fetch(
            buildDashboardApiUrl(),
            {
                headers: {
                    "Accept":
                        "application/json"
                }
            }
        );

        if (!response.ok) {
            throw new Error(
                `The Azure Function returned HTTP ${response.status}.`
            );
        }

        const data =
            await response.json();

        if (data?.error) {
            throw new Error(
                `Backend error: ${data.error}`
            );
        }

        validateResponse(
            data
        );

        updateMetadata(
            data
        );

        renderBarChart(
            data.charts.bar_chart
        );

        renderScatterChart(
            data.average_nutrition
        );

        renderHeatmap(
            data.average_nutrition
        );

        renderPieChart(
            data.charts.pie_chart
        );

        showStatus(
            successMessage,
            "success"
        );

    } catch (error) {
        console.error(
            "Unable to retrieve dashboard data:",
            error
        );

        showStatus(
            `Unable to load dashboard data. ${error.message}`,
            "error"
        );

    } finally {
        setLoadingState(
            false
        );
    }
}


/* =========================================================
   FETCH RECIPES
========================================================= */

async function fetchRecipes(
    page = 1
) {
    currentPage = Math.max(
        1,
        page
    );

    showStatus(
        "Loading recipes…"
    );

    try {
        const response = await fetch(
            buildRecipeApiUrl(
                currentPage
            ),
            {
                headers: {
                    "Accept":
                        "application/json"
                }
            }
        );

        if (!response.ok) {
            throw new Error(
                `Recipe API returned HTTP ${response.status}.`
            );
        }

        const data =
            await response.json();

        if (data?.error) {
            throw new Error(
                data.error
            );
        }

        const pagination =
            data.pagination || {};

        currentPage =
            Number(
                pagination.page ||
                currentPage
            );

        totalPages =
            Number(
                pagination.totalPages ||
                1
            );

        renderRecipeResults(
            data
        );

        updatePagination();

        const totalItems =
            Number(
                pagination.totalItems ||
                0
            );

        showStatus(
            `Loaded recipes successfully. Page ${currentPage} of ${totalPages}. Total matching recipes: ${totalItems}.`,
            "success"
        );

    } catch (error) {
        console.error(
            "Unable to retrieve recipes:",
            error
        );

        showStatus(
            `Unable to load recipes. ${error.message}`,
            "error"
        );
    }
}


/* =========================================================
   RECIPE RESULTS
========================================================= */

function getRecipeResultsContainer() {
    let container =
        document.getElementById(
            "recipe-results"
        );

    if (container) {
        return container;
    }

    container =
        document.createElement(
            "div"
        );

    container.id =
        "recipe-results";

    container.className =
        "recipe-results";

    const apiSection =
        elements.recipesButton.closest(
            ".interaction-section"
        );

    apiSection.appendChild(
        container
    );

    return container;
}


function renderRecipeResults(data) {
    const container =
        getRecipeResultsContainer();

    const items =
        Array.isArray(data.items)
            ? data.items
            : Array.isArray(data.recipes)
                ? data.recipes
                : [];

    container.replaceChildren();

    if (
        items.length === 0
    ) {
        const message =
            document.createElement(
                "p"
            );

        message.textContent =
            "No recipes matched the selected filters.";

        container.appendChild(
            message
        );

        return;
    }

    const heading =
        document.createElement(
            "h3"
        );

    heading.textContent =
        "Recipe Results";

    container.appendChild(
        heading
    );

    const list =
        document.createElement(
            "div"
        );

    list.className =
        "recipe-list";

    items.forEach(
        recipe => {
            const card =
                document.createElement(
                    "article"
                );

            card.className =
                "recipe-card";

            const name =
                recipe.recipe_name ||
                recipe.Recipe_name ||
                recipe.name ||
                "Recipe";

            const diet =
                recipe.diet_type ||
                recipe.Diet_type ||
                recipe.diet ||
                "Not specified";

            const cuisine =
                recipe.cuisine_type ||
                recipe.Cuisine_type ||
                recipe.cuisine ||
                "Not specified";

            const protein =
                recipe.protein ??
                recipe["Protein(g)"] ??
                "—";

            const carbs =
                recipe.carbs ??
                recipe["Carbs(g)"] ??
                "—";

            const fat =
                recipe.fat ??
                recipe["Fat(g)"] ??
                "—";

            const title =
                document.createElement(
                    "h4"
                );

            title.textContent =
                name;

            const details =
                document.createElement(
                    "p"
                );

            details.textContent =
                `${formatDietName(diet)} • ${cuisine}`;

            const nutrition =
                document.createElement(
                    "p"
                );

            nutrition.textContent =
                `Protein: ${protein} g | Carbs: ${carbs} g | Fat: ${fat} g`;

            card.append(
                title,
                details,
                nutrition
            );

            list.appendChild(
                card
            );
        }
    );

    container.appendChild(
        list
    );
}


/* =========================================================
   VALIDATION
========================================================= */

function validateResponse(
    data
) {
    if (
        !data ||
        typeof data !== "object"
    ) {
        throw new Error(
            "The response body is missing."
        );
    }

    if (
        !data.summary ||
        !data.metadata ||
        !data.average_nutrition ||
        !data.charts
    ) {
        throw new Error(
            "The response is missing required dashboard fields."
        );
    }

    validateSeries(
        data.charts.bar_chart,
        ["values"],
        "bar chart"
    );

    validateSeries(
        data.charts.pie_chart,
        ["values"],
        "pie chart"
    );

    validateSeries(
        data.average_nutrition,
        [
            "protein",
            "carbs",
            "fat"
        ],
        "nutrition"
    );
}


function validateSeries(
    series,
    valueKeys,
    name
) {
    if (
        !series ||
        !Array.isArray(
            series.labels
        )
    ) {
        throw new Error(
            `Missing ${name} labels.`
        );
    }

    valueKeys.forEach(
        key => {
            if (
                !Array.isArray(
                    series[key]
                ) ||
                series[key].length !==
                    series.labels.length
            ) {
                throw new Error(
                    `Invalid ${name} ${key} values.`
                );
            }
        }
    );
}


/* =========================================================
   METADATA
========================================================= */

function updateMetadata(
    data
) {
    elements.totalRecords.textContent =
        formatNumber(
            data.summary.total_records,
            0
        );

    elements.averageProtein.textContent =
        formatGrams(
            data.summary.avg_protein_overall
        );

    elements.averageCarbs.textContent =
        formatGrams(
            data.summary.avg_carbs_overall
        );

    elements.executionTime.textContent =
        `${formatNumber(
            data.metadata.execution_time_seconds,
            3
        )} s`;

    elements.datasetName.textContent =
        data.metadata.blob ||
        "Not provided";

    elements.datasetName.title =
        data.metadata.blob ||
        "";
}


/* =========================================================
   BAR CHART
========================================================= */

function renderBarChart(
    data
) {
    barChart?.destroy();

    barChart =
        new Chart(
            document.getElementById(
                "bar-chart"
            ),
            {
                type:
                    "bar",

                data: {
                    labels:
                        data.labels.map(
                            formatDietName
                        ),

                    datasets: [
                        {
                            label:
                                "Average Protein (g)",

                            data:
                                data.values,

                            backgroundColor:
                                "rgba(65, 100, 232, 0.82)",

                            borderColor:
                                "#4164E8",

                            borderWidth:
                                1,

                            borderRadius:
                                5
                        }
                    ]
                },

                options:
                    axisChartOptions(
                        "Diet type",
                        "Average protein (g)"
                    )
            }
        );
}


/* =========================================================
   SCATTER CHART
========================================================= */

function renderScatterChart(
    data
) {
    const points =
        data.labels.map(
            (diet, index) => ({
                x:
                    Number(
                        data.carbs[index]
                    ),

                y:
                    Number(
                        data.protein[index]
                    ),

                diet:
                    formatDietName(
                        diet
                    )
            })
        );

    scatterChart?.destroy();

    scatterChart =
        new Chart(
            document.getElementById(
                "scatter-chart"
            ),
            {
                type:
                    "scatter",

                data: {
                    datasets: [
                        {
                            label:
                                "Diet type",

                            data:
                                points,

                            backgroundColor:
                                "rgba(40, 152, 101, 0.82)",

                            borderColor:
                                "#1D754D",

                            pointRadius:
                                7,

                            pointHoverRadius:
                                9
                        }
                    ]
                },

                options: {
                    ...axisChartOptions(
                        "Average carbohydrates (g)",
                        "Average protein (g)"
                    ),

                    plugins: {
                        legend: {
                            display:
                                true,

                            position:
                                "bottom"
                        },

                        tooltip: {
                            callbacks: {
                                label(
                                    context
                                ) {
                                    const point =
                                        context.raw;

                                    return [
                                        `Diet: ${point.diet}`,

                                        `Carbohydrates: ${formatNumber(
                                            point.x,
                                            2
                                        )} g`,

                                        `Protein: ${formatNumber(
                                            point.y,
                                            2
                                        )} g`
                                    ];
                                }
                            }
                        }
                    }
                }
            }
        );
}


/* =========================================================
   HEATMAP
========================================================= */

function renderHeatmap(
    data
) {
    const nutrients = [
        {
            label:
                "Protein",

            values:
                data.protein
        },

        {
            label:
                "Carbs",

            values:
                data.carbs
        },

        {
            label:
                "Fat",

            values:
                data.fat
        }
    ];

    const allValues =
        nutrients
            .flatMap(
                nutrient =>
                    nutrient.values.map(
                        Number
                    )
            )
            .filter(
                Number.isFinite
            );

    const maximum =
        Math.max(
            ...allValues,
            1
        );

    const table =
        document.createElement(
            "table"
        );

    table.className =
        "heatmap-table";

    table.innerHTML =
        `<thead>
            <tr>
                <th scope="col">Diet type</th>
                ${nutrients
                    .map(
                        item =>
                            `<th scope="col">${item.label}</th>`
                    )
                    .join("")}
            </tr>
        </thead>`;

    const body =
        document.createElement(
            "tbody"
        );

    data.labels.forEach(
        (diet, rowIndex) => {
            const row =
                document.createElement(
                    "tr"
                );

            const label =
                document.createElement(
                    "th"
                );

            label.scope =
                "row";

            label.className =
                "diet-label";

            label.textContent =
                formatDietName(
                    diet
                );

            row.appendChild(
                label
            );

            nutrients.forEach(
                nutrient => {
                    const value =
                        Number(
                            nutrient.values[
                                rowIndex
                            ]
                        );

                    const intensity =
                        Number.isFinite(
                            value
                        )
                            ? value / maximum
                            : 0;

                    const cell =
                        document.createElement(
                            "td"
                        );

                    cell.textContent =
                        Number.isFinite(
                            value
                        )
                            ? formatNumber(
                                value,
                                1
                            )
                            : "—";

                    cell.style.backgroundColor =
                        `rgba(65, 100, 232, ${
                            0.12 +
                            intensity *
                            0.78
                        })`;

                    cell.style.color =
                        intensity > 0.55
                            ? "#FFFFFF"
                            : "#172554";

                    row.appendChild(
                        cell
                    );
                }
            );

            body.appendChild(
                row
            );
        }
    );

    table.appendChild(
        body
    );

    elements.heatmap.replaceChildren(
        table
    );
}


/* =========================================================
   PIE CHART
========================================================= */

function renderPieChart(
    data
) {
    pieChart?.destroy();

    pieChart =
        new Chart(
            document.getElementById(
                "pie-chart"
            ),
            {
                type:
                    "pie",

                data: {
                    labels:
                        data.labels.map(
                            formatDietName
                        ),

                    datasets: [
                        {
                            label:
                                "Records",

                            data:
                                data.values,

                            backgroundColor:
                                data.labels.map(
                                    (_, index) =>
                                        PIE_COLORS[
                                            index %
                                            PIE_COLORS.length
                                        ]
                                ),

                            borderColor:
                                "#FFFFFF",

                            borderWidth:
                                2
                        }
                    ]
                },

                options: {
                    responsive:
                        true,

                    maintainAspectRatio:
                        false,

                    plugins: {
                        legend: {
                            display:
                                true,

                            position:
                                "bottom"
                        }
                    }
                }
            }
        );
}


/* =========================================================
   CHART OPTIONS
========================================================= */

function axisChartOptions(
    xTitle,
    yTitle
) {
    return {
        responsive:
            true,

        maintainAspectRatio:
            false,

        plugins: {
            legend: {
                display:
                    true,

                position:
                    "bottom"
            }
        },

        scales: {
            x: {
                title: {
                    display:
                        true,

                    text:
                        xTitle
                },

                grid: {
                    display:
                        false
                }
            },

            y: {
                beginAtZero:
                    true,

                title: {
                    display:
                        true,

                    text:
                        yTitle
                }
            }
        }
    };
}


/* =========================================================
   SEARCH
========================================================= */

function handleSearch(
    event
) {
    if (
        event.key !== "Enter"
    ) {
        return;
    }

    event.preventDefault();

    currentPage =
        1;

    fetchRecipes(
        1
    );
}


/* =========================================================
   LOADING STATE
========================================================= */

function setLoadingState(
    isLoading
) {
    requestInProgress =
        isLoading;

    elements.insightsButton.disabled =
        isLoading;

    elements.dietFilter.disabled =
        isLoading;

    elements.insightsButton.textContent =
        isLoading
            ? "Loading..."
            : "Get Nutritional Insights";

    if (isLoading) {
        showStatus(
            "Loading nutritional insights…"
        );
    }
}


/* =========================================================
   STATUS
========================================================= */

function showStatus(
    message,
    type = ""
) {
    elements.statusMessage.textContent =
        message;

    elements.statusMessage.className =
        `status-message${
            type
                ? ` ${type}`
                : ""
        }`;
}


/* =========================================================
   PAGINATION
========================================================= */

function updatePagination() {
    elements.previousPage.disabled =
        currentPage <= 1;

    elements.nextPage.disabled =
        currentPage >= totalPages;

    elements.pageButtons.forEach(
        (
            button,
            index
        ) => {
            let pageNumber;

            if (
                currentPage <= 1
            ) {
                pageNumber =
                    index + 1;
            } else {
                pageNumber =
                    currentPage +
                    index;
            }

            if (
                pageNumber >
                totalPages
            ) {
                pageNumber =
                    Math.max(
                        1,
                        totalPages -
                        (
                            elements.pageButtons.length -
                            index -
                            1
                        )
                    );
            }

            button.dataset.page =
                String(
                    pageNumber
                );

            button.textContent =
                String(
                    pageNumber
                );

            const active =
                pageNumber ===
                currentPage;

            button.classList.toggle(
                "active",
                active
            );

            if (active) {
                button.setAttribute(
                    "aria-current",
                    "page"
                );
            } else {
                button.removeAttribute(
                    "aria-current"
                );
            }
        }
    );
}


function changePage(
    page
) {
    const newPage =
        Math.min(
            totalPages,
            Math.max(
                1,
                page
            )
        );

    fetchRecipes(
        newPage
    );
}


/* =========================================================
   FORMATTERS
========================================================= */

function formatDietName(
    value
) {
    if (
        String(value)
            .toLowerCase() ===
        "all"
    ) {
        return "All Diet Types";
    }

    const name =
        String(value)
            .replace(
                /[_-]/g,
                " "
            )
            .replace(
                /\b\w/g,
                letter =>
                    letter.toUpperCase()
            );

    return (
        name.toLowerCase() ===
        "dash"
    )
        ? "DASH"
        : name;
}


function formatNumber(
    value,
    maximumFractionDigits
) {
    const number =
        Number(value);

    return Number.isFinite(
        number
    )
        ? new Intl.NumberFormat(
            undefined,
            {
                maximumFractionDigits
            }
        ).format(
            number
        )
        : "—";
}


function formatGrams(
    value
) {
    const number =
        formatNumber(
            value,
            2
        );

    return (
        number === "—"
    )
        ? number
        : `${number} g`;
}


/* =========================================================
   CACHE DOM ELEMENTS
========================================================= */

function cacheElements() {
    Object.assign(
        elements,
        {
            totalRecords:
                document.getElementById(
                    "total-records"
                ),

            averageProtein:
                document.getElementById(
                    "average-protein"
                ),

            averageCarbs:
                document.getElementById(
                    "average-carbs"
                ),

            executionTime:
                document.getElementById(
                    "execution-time"
                ),

            datasetName:
                document.getElementById(
                    "dataset-name"
                ),

            heatmap:
                document.getElementById(
                    "heatmap"
                ),

            dietSearch:
                document.getElementById(
                    "diet-search"
                ),

            dietFilter:
                document.getElementById(
                    "diet-filter"
                ),

            insightsButton:
                document.getElementById(
                    "insights-button"
                ),

            recipesButton:
                document.getElementById(
                    "recipes-button"
                ),

            clustersButton:
                document.getElementById(
                    "clusters-button"
                ),

            statusMessage:
                document.getElementById(
                    "status-message"
                ),

            previousPage:
                document.getElementById(
                    "previous-page"
                ),

            nextPage:
                document.getElementById(
                    "next-page"
                ),

            pageButtons:
                [
                    ...document.querySelectorAll(
                        ".page-button"
                    )
                ]
        }
    );
}


/* =========================================================
   INITIALIZE DASHBOARD
========================================================= */

function initializeDashboard() {
    if (
        dashboardInitialized
    ) {
        return;
    }

    dashboardInitialized =
        true;

    cacheElements();

    elements.dietFilter.addEventListener(
        "change",
        () => {
            currentPage =
                1;

            fetchDashboardData(
                `${formatDietName(
                    elements.dietFilter.value
                )} dashboard loaded successfully.`
            );
        }
    );

    elements.dietSearch.addEventListener(
        "keydown",
        handleSearch
    );

    elements.insightsButton.addEventListener(
        "click",
        () =>
            fetchDashboardData()
    );

    elements.recipesButton.addEventListener(
        "click",
        () => {
            currentPage =
                1;

            fetchRecipes(
                1
            );
        }
    );

    elements.clustersButton.addEventListener(
        "click",
        () => {
            document
                .getElementById(
                    "heatmap-card"
                )
                .scrollIntoView(
                    {
                        behavior:
                            "smooth",

                        block:
                            "center"
                    }
                );

            showStatus(
                "The heatmap shows relative macronutrient intensity by diet type.",
                "info"
            );
        }
    );

    elements.previousPage.addEventListener(
        "click",
        () =>
            changePage(
                currentPage - 1
            )
    );

    elements.nextPage.addEventListener(
        "click",
        () =>
            changePage(
                currentPage + 1
            )
    );

    elements.pageButtons.forEach(
        button =>
            button.addEventListener(
                "click",
                () =>
                    changePage(
                        Number(
                            button.dataset.page
                        )
                    )
            )
    );

    updatePagination();
}


/* =========================================================
   AUTHENTICATED DASHBOARD START
========================================================= */

window.addEventListener(
    "dashboard-authenticated",
    () => {
        initializeDashboard();

        fetchDashboardData(
            "Dashboard loaded successfully."
        );
    }
);