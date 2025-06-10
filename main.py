import requests
import datetime
from google.transit import gtfs_realtime_pb2
import pandas as pd
import streamlit as st
import pydeck as pdk
import time
from scipy.spatial.distance import cdist
import numpy as np

pb_url = 'http://gtfs.edmonton.ca/TMGTFSRealTimeWebService/Vehicle/VehiclePositions.pb'

my_lat = st.number_input("Enter latitude")

my_lon = st.number_input("Enter longitude")

interval = 3

my_color = [245, 203, 66]
color0 = [60, 200, 20]
color1 = [20, 60, 200]
color2 = [200, 10, 50]

def update_csv(url):
    response = requests.get(url)

    feed = gtfs_realtime_pb2.FeedMessage()

    feed.ParseFromString(response.content)

    vehicle_data = []

    for entity in feed.entity:
        if entity.HasField('vehicle'):
            vehicle = entity.vehicle
            vehicle_data.append({
                'vehicle_id': vehicle.vehicle.id,
                'trip_id': vehicle.trip.trip_id,
                'latitude': vehicle.position.latitude,
                'longitude': vehicle.position.longitude,
                'timestamp': vehicle.timestamp,
            })

    vehicle_df = pd.DataFrame(vehicle_data)
    vehicle_df['trip_id'] = vehicle_df['trip_id'].astype(str)
    vehicle_df['timestamp'] = pd.to_datetime(vehicle_df['timestamp'], unit = 's')

    trips_df = pd.read_csv('trips.txt')
    trips_df['trip_id'] = trips_df['trip_id'].astype(str)
    merged_df = pd.merge(vehicle_df, trips_df[['trip_id', 'route_id']], on='trip_id', how='left')

    routes_df = pd.read_csv('routes.txt')
    final_df = pd.merge(merged_df, routes_df[['route_id', 'route_type', 'route_long_name', 'route_short_name']], on='route_id', how='left')

    vehicle_type_mapping = {
        0: 'Tram/Streetcar/Light rail',
        1: 'SubWay',
        2: 'Rail',
        3: 'Bus',
        4: 'Ferry',
        5: 'Cable car',
        6: 'Gondola/Funicular',
        7: 'Funicular'
    }

    final_df['vehicle_type'] = final_df['route_type'].map(vehicle_type_mapping)

    final_df[['vehicle_id', 'vehicle_type', 'latitude', 'longitude', 'route_short_name', 'route_long_name']].to_csv("vehicle_data_full.csv", index=False)
    r = pd.read_csv("vehicle_data_full.csv")
    return r

def haversine_vec(lat_lon_array, point):
    lat_lon_array = np.radians(lat_lon_array)
    point = np.radians(point)

    dlat = lat_lon_array[:, 0] - point[0]
    dlon = lat_lon_array[:, 1] - point[1]

    a = np.sin(dlat / 2.0)**2 + np.cos(point[0]) * np.cos(lat_lon_array[:, 0]) * np.sin(dlon / 2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    km = 6371 * c
    return km

st.title("Live Edmonton Transit Tracker")

while True:
    df = update_csv(pb_url)

    coords = df[['latitude', 'longitude']].to_numpy()
    df['distance'] = haversine_vec(coords, [my_lat, my_lon])
    df['label'] = "Vehicle information"

    user_location = pd.DataFrame({
        'latitude': [my_lat],
        'longitude': [my_lon],
        'color': [my_color],
        'label' : ['You are here'],
        'vehicle_type' : "",
        'route_short_name': "",
        'route_long_name': "",
        'distance': 0
    })

    vehicle_layer0 = pdk.Layer(
        "ScatterplotLayer",
        data=df[df['distance'] < interval],
        get_position='[longitude, latitude]',
        get_color=color0,
        get_radius=100,
        pickable = True,
    )

    vehicle_layer1 = pdk.Layer(
        "ScatterplotLayer",
        data=df[(df['distance'] >= interval) & (df['distance'] < interval * 2)],
        get_position='[longitude, latitude]',
        get_color=color1,
        get_radius=100,
        pickable = True,
    )

    vehicle_layer2 = pdk.Layer(
        "ScatterplotLayer",
        data=df[(df['distance'] >= interval * 2) & (df['distance'] < interval * 3)],
        get_position='[longitude, latitude]',
        get_color=color2,
        get_radius=100,
        pickable = True,
    )

    user_layer = pdk.Layer(
        "ScatterplotLayer",
        data=user_location,
        get_position='[longitude, latitude]',
        get_color='color',
        get_radius=150,
        pickable=True,
    )

    # Center the map view
    view_state = pdk.ViewState(
        latitude=my_lat,
        longitude=my_lon,
        zoom=13
    )

    tooltip = {
        "html": "<b>{label}</b><br/><b>Vehicle Type:</b> {vehicle_type} <br/> <b>Route:</b> {route_short_name} {route_long_name}<br/><b>Distance to destination:</b> {distance} km",
        "style": {"backgroundColor": "steelblue", "color": "white"}
    }

    # Render map with both layers
    st.pydeck_chart(pdk.Deck(
        layers=[vehicle_layer0, vehicle_layer1, vehicle_layer2, user_layer],
        initial_view_state=view_state,
        map_style='mapbox://styles/mapbox/light-v9',
        tooltip=tooltip
    ))

    selected = st.dataframe(df[['vehicle_id', 'vehicle_type', 'route_short_name', 'route_long_name', 'distance']])

    time.sleep(4)
    st.rerun()
    