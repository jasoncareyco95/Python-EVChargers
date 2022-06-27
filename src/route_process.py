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
#                 evc_data = evc_data.iloc[0:pre_built]
                outcome = simulate_trip(route, start_pos, end_pos, evc_data, route_dist, fuel_dist)
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
    with open(file_name, 'wb') as f:
        pickle.dump([evc_data, res], f)

    return None