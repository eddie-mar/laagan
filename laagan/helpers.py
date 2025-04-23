import googlemaps
import os
import requests
import threading
import time

from datetime import datetime
from functools import wraps
from flask import session, redirect, url_for, flash
from pprint import pprint

JAVASCRIPT_MAPS_API_KEY = 'AIzaSyDLDFyHQihmHzL0cSbCM09v_h8TLTyW314'
API_KEY = 'AIzaSyDVFeGFwyK2VG6NA6_mz0N-dOF80pghfEo'

map_client = googlemaps.Client(API_KEY)

def login_required(f):
     @wraps(f)
     def decorated_function(*args, **kwargs):
          if session.get('user_id') is None:
               flash('Log-in required', 'warning')
               return redirect(url_for('login'))
          return f(*args, **kwargs)
     return decorated_function

def get_wiki(address):
    wiki = "https://en.wikipedia.org/w/api.php"
    params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "exintro": True,
            "explaintext": True,
            "titles": address
    }
    data = requests.get(wiki, params).json()
    pages = data.get("query", {}).get("pages", {})
    for page_id, page_info in pages.items():
            if page_id != "-1":  # Check if the page exists
                return page_info.get("extract", None)
    return None

def place_search(place):
    try:
        response = map_client.places_autocomplete(place)
    except:
         return
    places = []
    for place in response:
        data = {}
        data['name'] = place.get('description', 'Error retrieving place name')
        data['place_id'] = place.get('place_id', None)
        places.append(data)
    
    for idx in range(len(places)):
        places[idx]['ok'] = False

        id = places[idx]['place_id']
        if id is None: continue

        response = map_client.place(id)
        if response['status'] != 'OK': continue
        # putting small description
        response = response['result']
        if response.get('editorial_summary', None):   # try editorial_summary googleapi
            places[idx]['overview'] = response['editorial_summary']['overview']
        else:     # try wikipedia
            overview = get_wiki(places[idx]['name'])
            if overview is None:
                 overview = f"{response['formatted_address']}. \nLocated at lat: {response['geometry']['location']['lat']:.2f}, lng: {response['geometry']['location']['lng']:.2f}."
            places[idx]['overview'] = overview
        
        if response.get('photos', None):
            photo_ref = response['photos'][0]['photo_reference']
            filename = download_google_photo(photo_ref, places[idx]['name'])
            places[idx]['photo'] = filename
        else:
             places[idx]['photo'] = None

        places[idx]['location'] = response['geometry']['location']

        places[idx]['ok'] = True

    return places

'''
          places = [{
               'name': ,
               'place_id': ,
               'overview': ,
               'photo' = filename,
               'location' = ,
               'ok' = ,
          }, {}, {}, . . ]
'''

                 
                 
def download_google_photo(photo_ref, photoname, max_height=400, folder='static/google_photos'):
     UPLOAD_FOLDER = os.path.join(os.getcwd(), folder) # make directory
     os.makedirs(UPLOAD_FOLDER, exist_ok=True)

     filename = f'{photoname}.jpg'
     while filename.find('/') != -1:
          filename = filename[:filename.find('/')] + filename[filename.find('/') + 2 :]

     file_path = os.path.join(UPLOAD_FOLDER, filename)

     if os.path.exists(file_path):
          return filename
     
     response = map_client.places_photo(photo_ref, max_height=max_height)
     if not response:
          return
     else:
          with open(file_path, 'wb') as photo:
               for chunk in response:
                    photo.write(chunk)
          return filename
     

def nearby_search(location, radius):
     results = []
     def api_search(location, radius, type, results):
          response = map_client.places_nearby(location=location, radius=radius, keyword=type)
          results.extend(response.get('results', []))
          next_page_token = response.get('next_page_token')

          while next_page_token:
               time.sleep(2)       # google requires 2 seconds for accessing next page results. slows my process. streamline in future
               response = map_client.places_nearby(page_token=next_page_token)
               results.extend(response.get('results', []))

               next_page_token = response.get('next_page_token')
     t = time.time()
     
     # use threading to multitask different keywords
     tourist_spots = threading.Thread(target=api_search, args=(location, radius, 'tourist spots', results))
     scenic_spots = threading.Thread(target=api_search, args=(location, radius, 'scenic spots', results))
     islands = threading.Thread(target=api_search, args=(location, radius, 'islands', results))

     tourist_spots.start()
     scenic_spots.start()
     islands.start()

     tourist_spots.join()
     scenic_spots.join()
     islands.join()

     print(f'Time took for nearby search: {time.time() - t}')

     sorted_results = sorted(results, key=lambda x: x.get('user_ratings_total', 0), reverse=True)

     final = []
     final_names = set()
     for place in sorted_results:
          if place['name'] in final_names:   # might produce multiple results for diffrent keyword search
               continue
          data = {}
          data['name'] = place['name']
          final_names.add(data['name'])

          data['location'] = place['geometry']['location']
          data['place_id'] = place['place_id']
          data['rating'] = place.get('rating', 'N/A')
          data['user_ratings_total'] = place.get('user_ratings_total', 0)
          
          if place.get('photos', None):
               photo_ref = place['photos'][0]['photo_reference']
               filename = download_google_photo(photo_ref, data['name'], folder=f'static/google_photos/{location}')
               data['photos'] = filename
               data['photo_loc'] = f'static/google_photos/{location}/{filename}'     # to cache and delete after x time. to download if will be used again
          else:
               data['photos'] = None
               data['photo_loc'] = None

          if place.get('vicinity', None):
               data['vicinity'] = place['vicinity']
          else:
               data['vicinity'] = data['location']
          
          final.append(data)
     
     for idx, place in enumerate(final):
          if place['user_ratings_total'] > 500 or idx < 20:      # most probable to have editorial summary
               response = map_client.place(place['place_id'])
               if response['status'] != 'OK':
                    continue
               place['overview'] = response['result']['editorial_summary']['overview'] if response['result'].get('editorial_summary', None) else None

     print(f'Time overall: {time.time() - t}')
     return final

'''
sorted_results = [{
     'name': ,
     'location': ,
     'place_id': ,
     'rating': ,
     'user_ratings_total': ,
     'photos': ,
     'photo_loc': ,
     'vicinity': ,
     'overview': ,
},
{}, {}, . . . {}]
'''
     

def parse_form(result):
     itinerary = {}
     itinerary['trips'] = []
     place = {}
     indices = ['idx', 'type', 'name', 'id', 'day', 'time-from', 'time-to', 'notes']
     itr = 0

     # save form data
     for key, value in result.items():
          if key == 'title':
               itinerary['itinerary_name'] = value
               continue
          elif key == 'location':
               itinerary['location'] = value
               continue
          elif key == 'description':
               itinerary['notes'] = value
               continue
          elif key == 'date-from':
               try:
                    itinerary['date-from'] = datetime.strptime(value, "%Y-%m-%d").date()
               except:
                    flash('Error in parsing date', 'danger')
                    return redirect(url_for('finalize', mode='init'))
               continue
          elif key == 'date-to':
               try:
                    itinerary['date-to'] = datetime.strptime(value, "%Y-%m-%d").date()
               except:
                    flash('Error in parsing date', 'danger')
                    return redirect(url_for('finalize', mode='init'))
               continue
          
          if not key.startswith(indices[itr]):
               flash('Fatal error. Data fields manipulated.', 'danger')
               return redirect(url_for('finalize', mode='init'))
          if indices[itr] != 'notes' and not value:
               flash('Input required in data fields except notes!', 'danger')
               return redirect(url_for('finalize', mode='init'))
          
          place[indices[itr]] = value
          itr += 1

          if itr == len(indices):     # finished recording for the entry
               itr = 0                 # reset iterator
               itinerary['trips'].append(place)    # add to trips
               place = {}              # reset dictionary

     return itinerary