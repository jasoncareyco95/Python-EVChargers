def calculate_route(pickup, dropoff, crs, return_trip = False):
    from geopandas import GeoDataFrame
    from geopandas import GeoSeries
    from polyline import decode
    from time import sleep
    from shapely.geometry import Point
    import pandas as pd
    import requests
    
    ## Convert pickup coordinates from UTM to CRS specified
    pickup_lon = pickup['point'].to_crs(crs).iloc[0]['geometry'].x
    pickup_lat = pickup['point'].to_crs(crs).iloc[0]['geometry'].y
    
    ## Convert dropoff coordinates from UTM to CRS specified
    dropoff_lon = dropoff['point'].to_crs(crs).iloc[0]['geometry'].x
    dropoff_lat = dropoff['point'].to_crs(crs).iloc[0]['geometry'].y
    
    loc = "{},{};{},{}".format(pickup_lon, pickup_lat, dropoff_lon, dropoff_lat)
    url = "http://router.project-osrm.org/route/v1/driving/"
    r = requests.get(url + loc + "?overview=full&annotations=true")
    if r.status_code != 200:
        print("Request returned unsuccessful status code... Retrying...")
        attempt = 1
        while (r.status_code != 200) & (attempt < 4):
            sleep(1)
            attempt += 1
            r = requests.get(url + loc + "?overview=full&annotations=true")
        if (r.status_code != 200) & (attempt >= 4):
            return None
  
    res = r.json()
    
    ## Get route details from response
    route_distances = [0, *res['routes'][0]['legs'][0]['annotation']['distance']]
    
    ## Collect main features of route from response
    route_coords = decode(res['routes'][0]['geometry'])
    route = GeoSeries([Point((x[1], x[0])) for x in route_coords], crs = wgs)
    
    ## Create route details data frame with distances and coords
    route_detail = pd.DataFrame({"distance": route_distances, "route": route})
    
    ## Return trip decision
    if return_trip == True:
        ## Generate a round trip by selecting all but last row and appending to route df
        ## Get return points and reverse order
        rd_return = route_detail.loc[0:len(route_detail) - 2][::-1]
        ## Row bind to route detail df
        route_detail_rb = pd.concat([route_detail, rd_return]).reset_index(drop = True)
        route_detail_rb['total_distance'] = route_detail_rb['distance'].cumsum()
        route_df = GeoDataFrame({
            'dist': route_detail_rb['distance'],
            'total_dist': route_detail_rb['total_distance'],
            'geometry': route_detail_rb['route']
        }, crs = wgs)
    else:
        route_detail['total_distance'] = route_detail['distance'].cumsum()
        route_df = GeoDataFrame({
            'dist': route_detail['distance'],
            'total_dist': route_detail['total_distance'],
            'geometry': route_detail['route']
        }, crs = wgs)
    
    start_point = GeoSeries(Point(res['waypoints'][0]['location'][0], res['waypoints'][0]['location'][1]), crs = wgs)
    end_point = GeoSeries(Point(res['waypoints'][1]['location'][0], res['waypoints'][1]['location'][1]), crs = wgs)
    distance = res['routes'][0]['distance']
    
    out = {'route':route,
           'route_detail':route_df,
           'start_point':start_point,
           'end_point':end_point,
           'distance':distance
          }

    return out