import os
import requests

from dotenv import load_dotenv

load_dotenv()

from flask import (
    Flask,
    jsonify,
    request,
    send_from_directory
)

from flask_cors import CORS

# =========================================================
# APP CONFIG
# =========================================================

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

FRONTEND_DIR = os.path.join(
    BASE_DIR,
    "Frontend"
)

# =========================================================
# FRONTEND ROUTES
# =========================================================

@app.route("/")
def home():
    return send_from_directory(
        FRONTEND_DIR,
        "index.html"
    )


@app.route("/Analysis/<path:filename>")
def analysis_files(filename):
    return send_from_directory(
        os.path.join(FRONTEND_DIR, "Analysis"),
        filename
    )


@app.route("/<path:filename>")
def frontend_files(filename):
    return send_from_directory(
        FRONTEND_DIR,
        filename
    )

# =========================================================
# WEATHER API
# =========================================================

@app.route("/weather", methods=["POST"])
def get_weather_insights():

    try:

        payload = request.get_json() or {}

        city = payload.get("city", "").strip()
        state = payload.get("state", "").strip()
        country = payload.get("country", "").strip()

        if not city or not state or not country:

            return jsonify({
                "success": False,
                "message": "Please fill all fields."
            }), 400

# ----------------------------------------------------
# STEP 1: Convert city → coordinates
# ----------------------------------------------------

        geo_response = requests.get(
            f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1",
            timeout=15
        )
        geo_response.raise_for_status()
        geo_data_response = geo_response.json()

        if not geo_data_response.get("results"):
            return jsonify({
                "success": False,
                "message": "Location not found."
            }), 404

        lat = geo_data_response["results"][0]["latitude"]
        lon = geo_data_response["results"][0]["longitude"]
        resolved_city = geo_data_response["results"][0].get("name", city)
        resolved_state = geo_data_response["results"][0].get("admin1", state)
        resolved_country = geo_data_response["results"][0].get("country", country)

        # ----------------------------------------------------
        # STEP 2 & 3: Current weather and Forecast
        # ----------------------------------------------------

        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
            "&daily=temperature_2m_max,precipitation_sum,wind_speed_10m_max"
            "&timezone=auto"
        )
        weather_response = requests.get(weather_url, timeout=15)
        weather_response.raise_for_status()
        weather_data = weather_response.json()

        current = weather_data.get("current", {})
        temp_val = current.get("temperature_2m", 0)
        humid_val = current.get("relative_humidity_2m", 50)
        wind_val = current.get("wind_speed_10m", 0)
        rain_val = current.get("precipitation", 0)

        # ----------------------------------------------------
        # RISK CALCULATIONS
        # ----------------------------------------------------

        flood_risk_metric = round(
            min(
                1.0,
                (
                    rain_val * 0.6 +
                    humid_val * 0.3 +
                    wind_val * 0.1
                ) / 100
            ),
            3
        )

        heat_risk_metric = round(
            min(
                1.0,
                (
                    max(temp_val - 25, 0) * 2 +
                    humid_val * 0.3
                ) / 100
            ),
            3
        )

        wildfire_risk_metric = round(
            min(
                1.0,
                (
                    max(temp_val - 32, 0) * 1.5 +
                    (100 - humid_val) * 0.5 +
                    wind_val * 0.2
                ) / 100
            ),
            3
        )

        cyclone_risk_metric = round(
            min(
                1.0,
                (
                    wind_val * 1.5 +
                    rain_val * 0.5
                ) / 100
            ),
            3
        )

        drought_risk_metric = round(
            min(
                1.0,
                (
                    max(temp_val - 28, 0) +
                    (100 - humid_val)
                ) / 100
            ),
            3
        )

        # ----------------------------------------------------
        # ALERTS
        # ----------------------------------------------------

        calculated_alerts = []

        if flood_risk_metric >= 0.6:
            calculated_alerts.append(
                "⚠ High Flood Risk Detected"
            )

        if heat_risk_metric >= 0.6:
            calculated_alerts.append(
                "🔥 Heatwave Conditions Possible"
            )

        if wildfire_risk_metric >= 0.6:
            calculated_alerts.append(
                "🌲 Elevated Wildfire Risk"
            )

        if cyclone_risk_metric >= 0.6:
            calculated_alerts.append(
                "🌀 Cyclone Risk Detected"
            )

        if drought_risk_metric >= 0.6:
            calculated_alerts.append(
                "☀ Drought Conditions Possible"
            )

        if not calculated_alerts:
            calculated_alerts.append(
                "✅ No major climate threats detected."
            )

        # ----------------------------------------------------
        # FORECAST GENERATION
        # ----------------------------------------------------

        forecast = []
        daily = weather_data.get("daily", {})
        times = daily.get("time", [])
        temps = daily.get("temperature_2m_max", [])
        rains = daily.get("precipitation_sum", [])
        winds = daily.get("wind_speed_10m_max", [])

        for i in range(min(5, len(times))):
            day_temp = temps[i] if i < len(temps) else temp_val
            day_humidity = humid_val # Open-Meteo doesn't easily provide daily humidity, use current
            day_rain = rains[i] if i < len(rains) else 0
            day_wind = winds[i] if i < len(winds) else wind_val

            forecast.append({
                "date": times[i],
                "temperature": round(day_temp, 1),
                "humidity": day_humidity,
                "rainfall": round(day_rain, 1),
                "wind_speed": round(day_wind, 1),
                "risks": {
                    "flood_risk": round(
                        min(
                            1.0,
                            (
                                day_rain * 0.6 +
                                day_humidity * 0.3 +
                                day_wind * 0.1
                            ) / 100
                        ),
                        3
                    ),
                    "heat_risk": round(
                        min(
                            1.0,
                            (
                                max(day_temp - 25, 0) * 2 +
                                day_humidity * 0.3
                            ) / 100
                        ),
                        3
                    ),
                    "wildfire_risk": round(
                        min(
                            1.0,
                            (
                                max(day_temp - 32, 0) * 1.5 +
                                (100 - day_humidity) * 0.5 +
                                day_wind * 0.2
                            ) / 100
                        ),
                        3
                    ),
                    "cyclone_risk": round(
                        min(
                            1.0,
                            (
                                day_wind * 1.5 +
                                day_rain * 0.5
                            ) / 100
                        ),
                        3
                    ),
                    "drought_risk": round(
                        min(
                            1.0,
                            (
                                max(day_temp - 28, 0) +
                                (100 - day_humidity)
                            ) / 100
                        ),
                        3
                    )
                }
            })

        return jsonify({

            "success": True,

            "location": {
                "city": resolved_city,
                "state": resolved_state,
                "country": resolved_country,
                "latitude": lat,
                "longitude": lon
            },

            "weather": {
                "temperature": temp_val,
                "humidity": humid_val,
                "rainfall": rain_val,
                "wind_speed": wind_val
            },

            "risks": {
    "flood_risk": round(flood_risk_metric, 3),
    "flood_risk_confidence": round(flood_risk_metric * 100, 1),
    "flood_risk_level": "HIGH" if flood_risk_metric >= 0.6 else "MEDIUM" if flood_risk_metric >= 0.3 else "LOW",
    "heat_risk": round(heat_risk_metric, 3),
    "heat_risk_confidence": round(heat_risk_metric * 100, 1),
    "heat_risk_level": "HIGH" if heat_risk_metric >= 0.6 else "MEDIUM" if heat_risk_metric >= 0.3 else "LOW",
    "wildfire_risk": round(wildfire_risk_metric, 3),
    "wildfire_risk_confidence": round(wildfire_risk_metric * 100, 1),
    "wildfire_risk_level": "HIGH" if wildfire_risk_metric >= 0.6 else "MEDIUM" if wildfire_risk_metric >= 0.3 else "LOW",
    "cyclone_risk": round(cyclone_risk_metric, 3),
    "cyclone_risk_confidence": round(cyclone_risk_metric * 100, 1),
    "cyclone_risk_level": "HIGH" if cyclone_risk_metric >= 0.6 else "MEDIUM" if cyclone_risk_metric >= 0.3 else "LOW",
    "drought_risk": round(drought_risk_metric, 3),
    "drought_risk_confidence": round(drought_risk_metric * 100, 1),
"drought_risk_level": "HIGH" if drought_risk_metric >= 0.6 else "MEDIUM" if drought_risk_metric >= 0.3 else "LOW",
            },

            "forecast": forecast,

            "alerts": calculated_alerts,

            "demo_mode": False

        }), 200

    except Exception as e:

        print("Weather API Error:", e)

        return jsonify({
            "success": False,
            "message": "Weather service unavailable."
        }), 500

# =========================================================
# REVERSE GEOCODE
# =========================================================

@app.route("/reverse-geocode", methods=["POST"])
def reverse_geocode():

    try:

        data = request.get_json()

        latitude = data.get("latitude")
        longitude = data.get("longitude")

        if latitude is None or longitude is None:

            return jsonify({
                "success": False,
                "message":
                "Latitude and longitude are required."
            })

        response = requests.get(
            f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={latitude}&longitude={longitude}&localityLanguage=en",
            timeout=20
        )

        if response.status_code != 200:

            return jsonify({
                "success": False,
                "message":
                "Reverse geocoding failed."
            })

        result = response.json()

        if not result or not result.get("city"):
            return jsonify({
                "success": False,
                "message":
                "Location not found."
            })

        return jsonify({
            "success": True,
            "city": result.get("city", ""),
            "state": result.get("principalSubdivision", ""),
            "country": result.get("countryName", "")
        })

    except Exception:

        return jsonify({
            "success": False,
            "message":
            "Reverse geocoding failed."
        })


# =========================================================
# GIS ALERT DATA (For tests)
# =========================================================

def fetch_gis_alert_data():
    """
    Fetches active alerts for the GIS map.
    Returns a tuple of (response_dict, status_code).
    """
    try:
        # Placeholder endpoint for GIS alert data
        resp = requests.get("https://api.weather.gov/alerts/active", timeout=10)
        resp.raise_for_status()
        return resp.json(), 200
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "Service Unavailable"}, 503
    except requests.exceptions.Timeout:
        return {"success": False, "message": "Gateway Timeout"}, 504
    except Exception as e:
        return {"success": False, "message": str(e)}, 500

# =========================================================
# CHATBOT API
# =========================================================

@app.route("/chatbot", methods=["POST"])
def chatbot():

    try:

        data = request.get_json()

        message = data.get(
            "message",
            ""
        ).lower()

        context = data.get("context", {})

        flood_risk = context.get(
            "flood_risk",
            0
        )

        heat_risk = context.get(
            "heat_risk",
            0
        )

        location = context.get(
            "location",
            "your area"
        )

        warning = ""

        # Try using Gemini API if key is available
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                prompt = f"You are ClimateBot, a helpful AI assistant for the Climate Shield application. Please answer this user question about weather, climate, or the application accurately and concisely: {message}"
                response = model.generate_content(prompt)
                
                return jsonify({
                    "success": True,
                    "response": response.text
                })
            except Exception as gemini_err:
                print("Gemini API Error:", str(gemini_err))
                # Fallback to static responses if Gemini fails

        # Static fallback responses
        responses = {

            "flood":
            "Floods are caused by heavy rainfall and overflowing rivers. Avoid low-lying areas.",

            "heatwave":
            "Heatwaves can cause dehydration and heat stroke. Stay hydrated and avoid direct sunlight.",

            "cyclone":
            "Cyclones bring strong winds and heavy rain. Follow evacuation advisories.",

            "earthquake":
            "During earthquakes, stay away from windows and take cover under sturdy furniture.",

            "climate":
            "Climate change increases the frequency of extreme weather events.",

            "rain":
            "Heavy rainfall may increase flood risks in vulnerable regions.",

            "drought":
            "Droughts occur when rainfall is significantly below normal levels. Conserve water and follow local water restrictions.",

            "wildfire":
            "Wildfires spread rapidly in hot, dry conditions. Follow evacuation orders and avoid smoke exposure.",

            "landslide":
            "Landslides can occur after heavy rainfall or earthquakes. Avoid steep slopes and follow local warnings."
        
        }

        for key in responses:

            if key in message:

                if flood_risk > 0.5:

                    warning = (
                        f"⚠ High Flood Risk detected in {location}. "
                        "Avoid low-lying areas and follow local alerts.\n\n"
                    )

                elif heat_risk > 0.5:

                    warning = (
                        f"🔥 High Heatwave Risk detected in {location}. "
                        "Stay hydrated and avoid prolonged outdoor exposure.\n\n"
                    )

                return jsonify({
                    "success": True,
                    "response": warning + responses[key]
                })

        default_response = (
            "ClimateBot is ready to help with floods, cyclones, heatwaves, and climate safety."
        )

        if flood_risk > 0.5:

            default_response = (
                f"⚠ High Flood Risk detected in {location}. "
                "Avoid low-lying areas and follow local alerts.\n\n"
                + default_response
            )

        elif heat_risk > 0.5:

            default_response = (
                f"🔥 High Heatwave Risk detected in {location}. "
                "Stay hydrated and avoid prolonged outdoor exposure.\n\n"
                + default_response
            )

        return jsonify({
            "success": True,
            "response": default_response
        })

    except Exception:

        return jsonify({
            "success": False,
            "message":
            "Chatbot unavailable."
        })

# =========================================================
# LOCAL RUN
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )