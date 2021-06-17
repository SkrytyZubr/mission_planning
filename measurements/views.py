from django.shortcuts import render
from django.core.files.storage import FileSystemStorage
import folium
import math
import geopandas as gpd
import fiona
from zipfile import ZipFile
import haversine as hs
import os
# Create your views here.

def calculate_distance_view(request):
    #save user file in 'media' folder
    if request.method == 'POST' and 'docfile' in request.FILES:
        uploaded_file = request.FILES['docfile']
        fs = FileSystemStorage()
        fs.save(uploaded_file.name, uploaded_file)

    #Add kml to fiona support
    fiona.drvsupport.supported_drivers['kml'] = 'rw' 
    fiona.drvsupport.supported_drivers['KML'] = 'rw'

    #open kmz file and unzpi kml
    try:
        kmz = ZipFile('media/'+uploaded_file.name, 'r')
    except UnboundLocalError:
        kmz = ZipFile('media/Beira.kmz', 'r')
    kmz.extract('doc.kml')
        

    #read kml file
    gdf = gpd.read_file('doc.kml', driver = 'KML')

    def get_geojson_grid(lower_left, upper_left, upper_right, lower_right, stepLat, stepLon, size):
        all_boxex = []

        myradians = math.atan2(upper_left[0]-upper_right[0], upper_right[1]-upper_left[1]) #calculate radians for lat
        myradians1 = math.atan2(upper_right[0]-lower_right[0], lower_right[1]-upper_right[1]) #caluculate radians for lon

        lat_step = [upper_right[0]] #list for points on lat
        lon_step = [upper_right[1]] #list for points on lon

        #calculate points for grid
        def points_coordinate(myradians, step, size):
            if size == 500:
                size = 0.500
            else:
                size = 1
            
            for point in range(step-1):

                R = 6378.1 #Radius of the Earth
                brng = myradians #Bearing is 90 degrees converted to radians.
                d = size #Distance in km.

                lat1 = math.radians(lat_step[-1]) #Current lat point converted to radians
                lon1 = math.radians(lon_step[-1]) #Current long point converted to radians

                #algorithms to calculate distances between points
                lat2 = math.asin( math.sin(lat1)*math.cos(d/R) +
                    math.cos(lat1)*math.sin(d/R)*math.cos(brng))

                lon2 = lon1 + math.atan2(math.sin(brng)*math.sin(d/R)*math.cos(lat1),
                            math.cos(d/R)-math.sin(lat1)*math.sin(lat2))

                #convert radians to degress
                lat2 = math.degrees(lat2)
                lon2 = math.degrees(lon2)

                #add points to lists
                lat_step.append(lat2)
                lon_step.append(lon2)

        points_coordinate(myradians, stepLat, size)
        del lat_step[:stepLat-1]#remove useless points from list

        points_coordinate(myradians1, stepLon, size)
        del lon_step[stepLon:]#remove useless points from list

        lat_stride = lat_step[-1] - lat_step[-2]
        lon_stride = lon_step[1] - lon_step[0]

        #making geojson 
        for lat in lat_step:
            for lon in lon_step:

                upper_left = [lon, lat + lat_stride]
                upper_right = [lon + lon_stride, lat + lat_stride]
                lower_right = [lon + lon_stride, lat]
                lower_left = [lon, lat]

                coordinates = [
                    upper_left,
                    upper_right,
                    lower_right,
                    lower_left,
                    upper_left
                ]

                geo_json = {'type': 'FeatureCollection',
                            'properties':{
                                'lower_left': lower_left,
                                'upper_right': upper_right,
                            },
                            'features':[]}
                grid_feature = {
                    'type':'Feature',
                    'geometry':{
                        'type':'Polygon',
                        'coordinates': [coordinates],
                    }
                }

                geo_json['features'].append(grid_feature)
                all_boxex.append(geo_json)
        return all_boxex

    p0 = gdf.centroid #central point for view location in folium map

    ymin, xmin, ymax, xmax  = gdf.total_bounds #most protruding points
    lower_left, upper_left, upper_right, lower_right  = [xmin, ymin], [xmin, ymax] , [xmax, ymax],[xmax, ymin]

    m = folium.Map(location=[p0.y, p0.x], zoom_start=14, tiles='OpenStreetMap') # making map

    size = 500 # 1000 # set squer size 

    #calculate how many squers will sweep away at lon and lat
    leftUp = hs.haversine(upper_left, upper_right, unit='m')
    stepLat = math.ceil(leftUp/size)
    leftDown = hs.haversine(upper_left, lower_left, unit='m')
    stepLon = math.ceil(leftDown/size)

    #make grid
    grid = get_geojson_grid(lower_left, upper_left, upper_right, lower_right ,stepLat, stepLon, size)

    #setting for gird
    for i, geo_json in enumerate(grid):
        color = None
        gj = folium.GeoJson(geo_json, style_function=lambda feature, color=color: {
                                                                            'fillColor': color,
                                                                            'color':"black",
                                                                            'weight': 0.5,
                                                                            'dashArray': '5, 5',
                                                                            'fillOpacity': 0.4,
                                                                        })
        popup = folium.Popup("example popup {}".format(i))
        gj.add_child(popup)
        m.add_child(gj)

    #setting for map
    for _, r in gdf.iterrows():
        sim_geo = gpd.GeoSeries(r['geometry'])
        geo_j = sim_geo.to_json()
        geo_j = folium.GeoJson(data=geo_j, style_function=lambda x: {'fillColor': 'orange'})
        geo_j.add_to(m)
    
    m = m._repr_html_()

    context = {
        'map': m,
    }

    #remove useless files
    file_list = os.listdir('media')
    if file_list[-1] == 'Beira.kmz':
        None
    else:
        os.remove('media/'+file_list[-1])

    return render(request, 'measurements/main.html', context)