import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium

# -------- SETTINGS --------
OPENWEATHER_API_KEY = "7fbd1bf75b3b13c4a9e281be3443a83f"
CSV_PATH = "data/hotels_sample.csv"

# -------- HELPERS --------
def parse_lat_lon(map_val):
    try:
        parts = str(map_val).strip().split('|')
        if len(parts) != 2:
            return None, None
        lat, lon = map(float, parts)
        return lat, lon
    except:
        return None, None

@st.cache_data
def load_data():
    df = pd.read_csv(CSV_PATH, encoding="ISO-8859-1")
    df['Latitude'], df['Longitude'] = zip(*df['Map'].apply(parse_lat_lon))
    return df.dropna(subset=['Latitude', 'Longitude'])

def get_aqi_for_coords(lat, lon):
    try:
        url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}"
        response = requests.get(url)
        data = response.json()
        return data['list'][0]['main']['aqi']  # AQI scale: 1 = Good, 5 = Very Poor
    except:
        return None

def calculate_score(noise_score, aqi, hotel_rating, preference):
    try:
        rating_score = float(hotel_rating)
    except:
        rating_score = 0.0

    if aqi is None:
        aqi_score = 0
    elif aqi < 50:
        aqi_score = 5
    elif aqi < 100:
        aqi_score = 3
    else:
        aqi_score = 1

    if preference == "Quiet Area":
        return (noise_score * 0.6) + (rating_score * 0.3) + (aqi_score * 0.1)
    elif preference == "Clean Air":
        return (noise_score * 0.3) + (rating_score * 0.3) + (aqi_score * 0.4)
    else:
        return (noise_score * 0.4) + (rating_score * 0.3) + (aqi_score * 0.3)

def label_noise(score):
    return "Quiet" if score == 5 else "Moderate" if score == 3 else "Noisy"

def label_aqi(aqi):
    if aqi is None:
        return "Unknown"
    elif aqi < 50:
        return "Good"
    elif aqi < 100:
        return "Moderate"
    elif aqi < 150:
        return "Unhealthy for Sensitive Groups"
    elif aqi < 200:
        return "Unhealthy"
    else:
        return "Very Poor"

# -------- UI --------
st.set_page_config(page_title="TravelSmart – Noise & Air Quality Finder", layout="wide")

st.title("🌍 TravelSmart – Hotel Noise & Air Quality Recommender")
st.markdown("""
Use this app to discover the quietest and cleanest hotels in your destination city, 
based on real environmental data and guest reviews.
""")

df = load_data()

# --- User Filters
city = st.selectbox("🌆 Select a City", sorted(df['cityName'].dropna().unique()))
preference = st.radio("🎯 What do you value most?", ["Quiet Area", "Clean Air", "Both"])
search_term = st.text_input("🔎 Search for a hotel (optional)", "")

filtered_df = df[df['cityName'] == city]
if search_term:
    filtered_df = filtered_df[filtered_df['HotelName'].str.contains(search_term, case=False, na=False)]

# -------- Results
results = []
with st.spinner("Fetching air quality data..."):
    for _, row in filtered_df.iterrows():
        noise_score = 5 if row.get('NoiseCategory') == 'Low Noise' else 3 if row.get('NoiseCategory') == 'Moderate Noise' else 1
        aqi = get_aqi_for_coords(row['Latitude'], row['Longitude'])
        if aqi is None:
            continue
        final_score = calculate_score(noise_score, aqi, row['HotelRating'], preference)
        results.append({
            "Hotel": row['HotelName'],
            "Noise": label_noise(noise_score),
            "Air Quality": label_aqi(aqi),
            "Rating": row['HotelRating'],
            "Score": final_score,
            "Lat": row['Latitude'],
            "Lon": row['Longitude']
        })

if results:
    result_df = pd.DataFrame(results).sort_values(by="Score", ascending=False).head(10)

    st.subheader("🏨 Top Hotel Recommendations")
    styled_df = result_df[["Hotel", "Noise", "Air Quality", "Rating", "Score"]].rename(columns={
        "Hotel": "🏨 Hotel Name",
        "Noise": "🔊 Noise Level",
        "Air Quality": "🌫️ Air Quality",
        "Rating": "⭐ Hotel Rating",
        "Score": "📊 Composite Score"
    })
    st.dataframe(styled_df, use_container_width=True)

    # -------- MAP
    st.subheader("🗺️ Map View")
    m = folium.Map(location=[result_df.iloc[0]['Lat'], result_df.iloc[0]['Lon']], zoom_start=13)
    for _, row in result_df.iterrows():
        folium.Marker(
            location=[row['Lat'], row['Lon']],
            popup=f"<b>{row['Hotel']}</b><br>Noise: {row['Noise']}<br>Air Quality: {row['Air Quality']}<br>Rating: {row['Rating']}⭐",
            tooltip=row['Hotel']
        ).add_to(m)
    st_folium(m, width=700, height=500)
else:
    st.warning("No matching hotels found for the selected city or search term.")
