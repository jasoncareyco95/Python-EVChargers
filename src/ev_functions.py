## Create sample point function for starting and ending positions ----
def sample_point(data, crs):
    from random import sample
    from shapely.geometry import Point
    from geopandas import GeoDataFrame
    
    data = data.copy()
    
    ## sample one random row from 'data'
    sample_road_row = sample(range(len(data)), 1)

    ## Filter down 'data' to sample road
    sample_road_data = data.loc[sample_road_row].reset_index(drop = True)

    ## Randomly select a pair of coordinates within the road we've selected as a starting point
    sample_road_coords = list(sample_road_data.geometry[0].coords)
    sample_index = sample(range(len(sample_road_coords)), 1)
    sample_geo = Point(list(sample_road_coords[sample_index[0]]))

    point_df = GeoDataFrame({'geometry': [sample_geo]}, crs = "EPSG:32613")
    point_df = point_df.to_crs(crs)

    ## Return a list with the corresponding sample road row number in 'data' and a geometry object
    return({
        "road_row_num" : sample_road_data.record[0], 
        "point" : point_df
    })

## Get starting point function ----
def get_start_point(df, crs):
    from pandas import DataFrame
    from geopandas import GeoDataFrame
    
    data = df.copy()

    ## Filter to roadways of level 3 (minor/residential roadways)
    valid_startpoints = data[data["level"] == 3].reset_index(drop = True)

    return sample_point(valid_startpoints, crs)

## Get ending point function ----
def get_end_point(df, start_pos, route_dist, crs):
    from pandas import DataFrame
    from geopandas import GeoDataFrame
    
    data = df.copy()
    sp = start_pos['point'].to_crs("EPSG:32613")
    
    ## Create distances column used for filtering points
    data['distances'] = data['geometry'].distance(sp.geometry[0])
    
    ## Filter points to distances that are further than half of route_dist
    valid_endpoints = data[data['distances'] >= (route_dist / 2)].reset_index(drop = True)
    
    return sample_point(valid_endpoints, crs)

## Calculate route between points ----
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
    route = GeoSeries([Point((x[1], x[0])) for x in route_coords], crs = crs)
    
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
        }, crs = crs)
    else:
        route_detail['total_distance'] = route_detail['distance'].cumsum()
        route_df = GeoDataFrame({
            'dist': route_detail['distance'],
            'total_dist': route_detail['total_distance'],
            'geometry': route_detail['route']
        }, crs = crs)
    
    start_point = GeoSeries(Point(res['waypoints'][0]['location'][0], res['waypoints'][0]['location'][1]), crs = crs)
    end_point = GeoSeries(Point(res['waypoints'][1]['location'][0], res['waypoints'][1]['location'][1]), crs = crs)
    distance = res['routes'][0]['distance']
    
    out = {'route':route,
           'route_detail':route_df,
           'start_point':start_point,
           'end_point':end_point,
           'distance':distance
          }

    return out
    
## Simulation Helpers ----
def nearest_chg_pt(pos1, evc_data):
    from pandas import DataFrame
    from geopandas import GeoSeries
    from shapely.ops import nearest_points
    
    chg_pts = evc_data['geometry'].unary_union
    return GeoSeries(nearest_points(pos1, chg_pts))[1]

def format_coord(pos, crs):
    from geopandas import GeoDataFrame
    
    return {'point': GeoDataFrame({'geometry': [pos]}, crs = crs)}

## Simulate trip function ----
def simulate_trip(route, start_pos, end_pos, evc_data, route_dist, fuel_dist, crs, alpha = 2):
    from pandas import DataFrame
    from numpy import random
    from geopandas import GeoSeries
    
    # alpha = 2
    sim_route = route['route']
    sim_route_details = route['route_detail']

    rng = route_dist
    route_index = 0
    trip_direction = 1

    while rng > 0 & trip_direction < 3:
        
        ## Decrease range
        rng -= sim_route_details['dist'].loc[route_index]

        ## Check if we need to refuel
        if rng < fuel_dist:

            ## Get our current location and find the nearest charger
            current_location = sim_route_details['geometry'].loc[route_index]
            nearest_charger = nearest_chg_pt(current_location, evc_data)

            ## Find the number of chargers at the charging station
            nearest_chargers = evc_data[evc_data['geometry'] == nearest_charger]['nm_chrg']
            for row in nearest_chargers.index:
                num_chgs = nearest_chargers.iloc[0]
            
                ## Use a Poisson RV to estimate number of available chargers at the station
                in_use = random.poisson(alpha, 1)

                if in_use >= num_chgs:
                    charger_available = False
                else:
                    charger_available = True
                    break

            if charger_available == True:
                ## Get coordinates for current location and charging station
                pos1 = format_coord(current_location, crs)
                pos2 = format_coord(nearest_charger, crs)

                ## Generate new route to charger
                re_route = calculate_route(pos1, pos2, crs, return_trip = False)

                ## Simulate travel to the charger
                for i in range(len(re_route['route_detail'])):
                    rng -= re_route['route_detail'].loc[i]['dist']
                    if rng <= 0:
                        outcome = DataFrame({
                            "fll_ddr": None,
                            "nm_chrg": 4,
                            "fal_typ": "Chargers out of range",
                            "geometry": [re_route['route_detail'].loc[i]['geometry']]
                        })
                        return outcome

                ## Refuel the vehicle
                rng = route_dist

                ## Re-route to the next point of interest (starting or ending position)
                if (route_index < len(sim_route) - 1) & (trip_direction == 1):

                    ## Generate new route from current location to next point of interest
                    new_route = calculate_route(
                        format_coord(nearest_charger, crs),
                        end_pos,
                        crs,
                        return_trip = False
                    )

                    sim_route = new_route['route']
                    sim_route_details = new_route['route_detail']

                    ## Reset the route index
                    route_index = 0

                else:

                    ## Generate new route from current location to next point of interest
                    new_route = calculate_route(
                        format_coord(nearest_charger, crs),
                        start_pos,
                        crs,
                        return_trip = False
                    )

                    sim_route = new_route['route']
                    sim_route_details = new_route['route_detail']

                    ## Reset the route index
                    route_index = 0

            else:
                ## Charger is unavailable
                if rng <= 0:
                    outcome = DataFrame({
                        "fll_ddr": None,
                        "nm_chrg": 4,
                        "fal_typ": "Chargers unavailable",
                        "geometry": [GeoSeries(current_location, crs = crs)]
                    })
                    return outcome
                
        if (route_index == len(sim_route) - 1) & (trip_direction == 1):

            new_route = calculate_route(
                format_coord(sim_route.loc[route_index], crs = crs),
                start_pos,
                crs,
                return_trip = False
            )

            sim_route = new_route['route']
            sim_route_details = new_route['route_detail']

            route_index = 0
            trip_direction = 2

        elif (route_index == len(sim_route) - 1) & (trip_direction == 2):

            return None

        ## Increment route index    
        route_index += 1

    return None

## Route process function ----
def route_process(road_data, evc_data, route_dist, fuel_dist, crs, pre_built, n_sim = 1):
    from datetime import date
    import pickle
    import pandas as pd
    
    res = []
    k = 0
    today = date.today()
    
    while k < n_sim:

        start_pos = get_start_point(road_data, crs)
        end_pos = get_end_point(road_data, start_pos, route_dist, crs)

        route = calculate_route(start_pos, end_pos, crs, return_trip = True)

        if route is not None:
            route_total_dist = route['route_detail']['total_dist'].iloc[-1]

        if (route is not None) & (route_total_dist > route_dist):
            k += 1
            print("Simulation attempt:", k)

            ## Simulate trip given the route fits our criteria for appropriate distance
            try:
                outcome = simulate_trip(route, start_pos, end_pos, evc_data, route_dist, fuel_dist, crs)
                res.append(0 if outcome is None else 1)
            
                if outcome is not None:

                    evc_data = pd.concat([evc_data, outcome]).reset_index(drop = True)
                    print("New charger added. Fail Type:", outcome['fal_typ'].iloc[0])
                    
            except:
                print("Creating pickle!")
                file_name = 'route_' + today.strftime("%d_%m_%Y") + ".pkl"
                with open(file_name, 'wb') as f:
                    pickle.dump([evc_data, route], f)
                break
    
    file_name = 'outcomes_' + today.strftime("%d_%m_%Y") + ".pkl"

    ## Save outcomes to file
    print("Simulations completed. Creating pickle!")
    
    with open(file_name, 'wb') as f:
        pickle.dump([evc_data, res], f)

    return None