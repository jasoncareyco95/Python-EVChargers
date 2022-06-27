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
def simulate_trip(route, start_pos, end_pos, evc_data, route_dist, fuel_dist, alpha = 2):
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
                pos1 = format_coord(current_location, wgs)
                pos2 = format_coord(nearest_charger, wgs)

                ## Generate new route to charger
                re_route = calculate_route(pos1, pos2, wgs, return_trip = False)

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
                        format_coord(nearest_charger, wgs),
                        end_pos,
                        wgs,
                        return_trip = False
                    )

                    sim_route = new_route['route']
                    sim_route_details = new_route['route_detail']

                    ## Reset the route index
                    route_index = 0

                else:

                    ## Generate new route from current location to next point of interest
                    new_route = calculate_route(
                        format_coord(nearest_charger, wgs),
                        start_pos,
                        wgs,
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
                        "geometry": [GeoSeries(current_location, crs = wgs)]
                    })
                    return outcome
                
        if (route_index == len(sim_route) - 1) & (trip_direction == 1):

            new_route = calculate_route(
                format_coord(sim_route.loc[route_index], crs = wgs),
                start_pos,
                wgs,
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