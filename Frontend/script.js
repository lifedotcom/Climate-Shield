// ==========================================
// CRITICAL FIX FOR ISSUE #84: Global Chart Tracker
// ==========================================
let climateChartInstance = null;

// Hook into Chart.js to intercept creation and destroy older leaking instances automatically
if (window.Chart) {
    const OriginalChart = window.Chart;
    window.Chart = function(ctx, config) {
        if (climateChartInstance !== null && typeof climateChartInstance.destroy === 'function') {
            try {
                climateChartInstance.destroy();
            } catch (e) {
                console.warn("Instance cleanup handled:", e);
            }
        }
        climateChartInstance = new OriginalChart(ctx, config);
        return climateChartInstance;
    };
    // Copy static properties over to the patched constructor
    Object.assign(window.Chart, OriginalChart);
}

// ==========================================
// Your Original Weather API Logic
// ==========================================
function resolveApiUrl(){
    // Prefer explicit backend URL injected by the HTML page.
    // Set window.__BACKEND_URL__ to your Flask/Gunicorn service base URL in production.
    if (window.__BACKEND_URL__ && typeof window.__BACKEND_URL__ === 'string' && window.__BACKEND_URL__.trim() !== '') {
        return window.__BACKEND_URL__.replace(/\/+$/, '') + '/weather';
    }

    // Local dev fallback.
    if (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost") {
        return "http://127.0.0.1:5000/weather";
    }


    // Production fallback: assume backend is reachable at same origin.
    // This is correct only when frontend and backend are served by the same host.
    return window.location.origin + "/weather";
}


const API_URL = resolveApiUrl();


async function getWeatherData(){
    const city = document.getElementById("city").value;
    const state = document.getElementById("state").value;
    const country = document.getElementById("country").value;
    const loading = document.getElementById("loading");
    const weatherCard = document.getElementById("weather-card");
    const alertBox = document.getElementById("alert-box");

    if(city.trim() === "" || state.trim() === "" || country.trim() === ""){
        alert("Please fill all fields.");
        return;
    }

    loading.classList.remove("hidden");
    weatherCard.classList.add("hidden");

    try{
        const response = await fetch(
            API_URL,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    city: city,
                    state: state,
                    country: country
                })
            }
        );

        const data = await response.json();
        loading.classList.add("hidden");

        if(!data.success){
            alert(data.message);
            return;
        }

        document.getElementById("location").innerText =
            `${data.location.city}, ${data.location.state}, ${data.location.country}`;

        document.getElementById("temperature").innerText = `${data.weather.temperature} °C`;
        document.getElementById("humidity").innerText = `${data.weather.humidity} %`;
        document.getElementById("rainfall").innerText = `${data.weather.rainfall} mm`;
        document.getElementById("wind").innerText = `${data.weather.wind_speed} km/h`;
        document.getElementById("flood-risk").innerText = data.risks.flood_risk;
        document.getElementById("heat-risk").innerText = data.risks.heat_risk;

        let alertsHTML = "";
        data.alerts.forEach(alertMessage => {
            alertsHTML += `
                <div class="notification">
                    ${alertMessage}
                </div>
            `;
        });

        alertBox.innerHTML = alertsHTML;
        alertBox.classList.remove("hidden");
        weatherCard.classList.remove("hidden");

    }catch(error){
        console.error(error);
        loading.classList.add("hidden");
        alert("Backend server is not running.");
    }
}

// ==========================================
// Lifecycle Clean-up Hook for Route Changes
// ==========================================
window.addEventListener('beforeunload', () => {
    if (climateChartInstance !== null && typeof climateChartInstance.destroy === 'function') {
        climateChartInstance.destroy();
    }
});
