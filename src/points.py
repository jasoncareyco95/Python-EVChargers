## Create sample point function for starting and ending positions ----
def sample_point(data, crs):
    from random import sample
    from shapely.geometry import Point
    
    data = all_roads_proj.copy()
    
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