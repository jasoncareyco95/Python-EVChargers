import ev_functions as evc
from geopandas import read_file
from geopandas import GeoDataFrame

all_roads = read_file('C:/Users/jason/Downloads/Datasets/ev_geospatial/all_roads.shp').to_crs('GCS_WGS84')
all_roads_proj = all_roads.to_crs("EPSG:32613")

## Read in chgs shape file
# chgs = gpd.read_file('/home/jcarey9/ev_chargers/data/alt_fuel_stations.shp').to_crs("GCS_WGS84")
chgs = read_file('C:/Users/jason/Downloads/Datasets/ev_geospatial/alt_fuel_stations.shp').to_crs('GCS_WGS84')
chgs_proj = chgs.to_crs("EPSG:32613")

pre_built = len(chgs)

## Create initial constants
route_dist = 402336
fuel_dist = route_dist * .25
n = 10000

## Get the CRS for future calculations between geometries
wgs = all_roads.crs
epsg = all_roads_proj.crs

sim_outcomes = evc.route_process(all_roads_proj, chgs, route_dist, fuel_dist, wgs, pre_built, n_sim = n)