# Imports
from datetime import datetime
from flask import Flask, flash, redirect, render_template, request, session, url_for, jsonify
from flask_session import Session
from sqlalchemy import or_, and_
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from helpers import JAVASCRIPT_MAPS_API_KEY, place_search, login_required, nearby_search, parse_form
from models import db, Users, Setting, Trip, Places, Itinerary, Types

import pprint
import random


# Configure
app = Flask(__name__)
app.config['DEBUG'] = True
app.secret_key = 'secret_key'

app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///laagan-database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)    

with app.app_context():
    db.create_all()

    types = ['Place', 'Activity', 'Hotel', 'Flight', 'Travel time', 'Other']
    for type in types:
        if not Types.query.filter_by(trip_type=type).first():
            db.session.add(Types(trip_type=type))
    
    db.session.commit()

# Routes
@app.route('/')
def index():
    session['nearby_search'] = None
    return render_template('main.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirmation = request.form.get('confirmation')
        email = request.form.get('email')

        # Check if fields are complete and password are the same
        if not all([username, password, confirmation, email]):
            flash('Please input in all fields!', 'danger')
            return redirect(url_for('register'))
        if password != confirmation:
            flash('Password does not match!', 'danger')
            return redirect(url_for('register'))
        
        # Check if username already exist
        if Users.query.filter(Users.username == username).first():
            flash('Username already exist', 'danger')
            return redirect(url_for('register'))
        
        new_user = Users(username=username, password=generate_password_hash(password), email=email)
        setting = Setting(user=new_user)

        db.session.add(new_user)
        db.session.add(setting)
        db.session.commit()

        flash('Account succesfully created', 'success')
        return redirect(url_for('login'))

    else:
        return render_template('register.html')
    

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
    
        if not all([username, password]):
            flash('Please input in all fields!', 'danger')
            return redirect(url_for('login'))

        # Check if user account exists
        user = Users.query.filter(Users.username == username).first()
        if user is None:
            flash('User does not exist', 'danger')
            return redirect(url_for('login'))
        if not check_password_hash(user.password, password):
            flash('Wrong Password', 'danger')
            return redirect(url_for('login'))
        
        session['user_id'] = user.id
        session['user_name'] = user.username
        setting = Setting.query.filter_by(user_id=session['user_id']).first()
        if setting is None:
            flash('Account does not exist. Fatal error', 'danger')
            session.clear()
            return redirect(url_for('index'))
        
        session['radius'] = setting.radius
        session['limit'] = setting.nearby_search_limit


        flash('Login successful', 'success')
        return redirect(url_for('index'))
        
    else:
        return render_template('login.html')
    

@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/setting', methods=['GET'])
def setting():
    user_data = Users.query.get(session['user_id'])
    if user_data is None:
        flash('Account does not exist. Fatal error', 'danger')
        session.clear()
        return redirect(url_for('index'))

    username = user_data.username
    email = user_data.email
    home_add = user_data.home_add

    setting_data = Setting.query.filter_by(user_id=session['user_id']).first()
    radius = setting_data.radius
    limit = setting_data.nearby_search_limit

    return render_template('settings.html', username=username, email=email, home_add=home_add, radius=radius, limit=limit)


@app.route('/edit-account', methods=['POST'])
def edit_account():
    username = request.form.get('new-username')
    email = request.form.get('new-email')
    home_add = request.form.get('new-homeAdd')

    if not all([username, email]):
        flash('Please input in all fields', 'danger')
        return redirect(url_for('setting'))
    
    if Users.query.filter(Users.username == username).first():
        if username != session['user_name']:
            flash('New username already used', 'danger')
            return redirect(url_for('setting'))
        
    user_data = Users.query.get(session['user_id'])
    if user_data is None:
        flash('Account does not exist. Fatal error', 'danger')
        session.clear()
        return redirect(url_for('index'))

    user_data.username = username
    user_data.email = email
    user_data.home_add = home_add
    db.session.commit()

    # change session['user_name']
    session['user_name'] = username

    flash('Details successfully updated', 'success')
    return redirect(url_for('setting'))


@app.route('/change-password', methods=['POST'])
def change_password():
    current = request.form.get('current-pass')
    change = request.form.get('change-pass')
    verify = request.form.get('verify-pass')

    if not all([current, change, verify]):
        flash('Please input in all fields', 'danger')
        return redirect(url_for('setting'))
    
    user = Users.query.get(session['user_id'])
    if user is None:
        flash('Account does not exist. Fatal error', 'danger')
        session.clear()
        return redirect(url_for('index'))

    if not check_password_hash(user.password, current):
        flash('Current password is incorrect', 'danger')
        return redirect(url_for('setting'))
    if change != verify:
        flash('New password does not match', 'danger')
        return redirect(url_for('setting'))

    user.password = generate_password_hash(change)
    db.session.commit()

    flash('Password changed successfully', 'success')
    return redirect(url_for('setting'))


@app.route('/delete-account', methods=['POST', 'DELETE'])
def delete_account():
    if request.method == 'POST' and request.form.get('_method') == 'DELETE':
        account = Users.query.get(session['user_id'])
        
        if account is None:
            flash("Account doesn't exist", 'danger')
            return redirect(url_for('settting'))
        
        db.session.delete(account)
        db.session.commit()
        session.clear()

        flash('Account deleted successfully', 'success')
        return redirect(url_for('login'))
    

@app.route('/change-setting', methods=['POST'])
def change_setting():
    new_radius = request.form.get('new-radius')
    new_limit = request.form.get('new-limit')

    if new_radius is None or new_limit is None:
        flash('Please input radius and limit', 'danger')
        return redirect(url_for('setting'))
    
    try:
        new_radius = float(new_radius)
        new_limit = int(new_limit)
    except ValueError:
        flash('Radius must be an integer or a decimal value. Limit must be an integer.', 'danger')
        return redirect(url_for('setting'))
    
    if new_radius > 250 or new_radius < 10:
        flash('Radius must be between 10 - 250 km', 'danger')
        return redirect(url_for('setting'))
    
    if new_limit > 250 or new_limit < 10:
        flash('Attractions search limit must be between 10 - 250', 'danger')
        return redirect(url_for('setting'))
    
    setting = Setting.query.filter_by(user_id=session['user_id']).first()
    if setting is None:
        flash('Account does not exist. Fatal error', 'danger')
        session.clear()
        return redirect(url_for('index'))
    
    setting.radius = new_radius
    setting.nearby_search_limit = new_limit
    db.session.commit()
    session['radius'] = setting.radius
    session['limit'] = setting.nearby_search_limit

    flash('Settings changed successfully', 'success')
    return redirect(url_for('setting'))


@app.route('/search', methods=['GET'])
def search():
    clear_session()
    query = request.args.get('q', ' ')
    places = place_search(query)
    if places is None:
        flash('No results. May have been invalid input or empty space', 'danger')
        return render_template('search.html', places=[])
    
    return render_template('search.html', places=places)

@app.route('/clear_session', methods=['POST'])
def clear_session():
    session.pop('nearby_search', None)
    session.pop('added', None)
    session.pop('title', None)
    session.pop('location', None)
    session.pop('finalize_mode', None)
    session.pop('trip_id', None)
    return '', 204 

@app.route('/planner/attractions/', methods=['GET'])
@login_required
def attractions():
    api_key = JAVASCRIPT_MAPS_API_KEY
    title = request.args.get('title') if 'title' not in session else session['title']
    page = request.args.get('page')
    location = request.args.get('location')
    place_per_page = 12

    if not page or not location or not title:
        flash('Location or page not found. Fatal error.', 'danger')
        return redirect(url_for('search'))
    
    session['location'] = location  # to use in other pages to access planner
    session['title'] = title

    try:
        page = int(page)
    except:
        flash('Page must be an integer', 'danger')
        return redirect(url_for('search'))  

    if session.get('nearby_search') is None:
        search = nearby_search(location, session['radius'] * 1000)
        session['nearby_search'] = search[:session['limit']]
        session['added'] = []   # initiate list of indices added to itinerary

    total_pages = ((len(session['nearby_search']) - 1) // place_per_page) + 1
    if page < 1: page = 1                           # clicking previous when page is 1
    elif page > total_pages: page = total_pages     # clicking next when page is at end

    if total_pages < 5:
        pages_to_display = [i for i in range(1, total_pages + 1)]
    else:
        if page == 1 or page - 2 == 0: 
            pages_to_display = [i for i in range(1, 6)]
        elif page == total_pages or page + 2 > total_pages:
            pages_to_display = [i for i in range(total_pages - 4, total_pages + 1)]
        else:
            pages_to_display = [page - 2, page - 1, page, page + 1, page + 2]
    
    # index to display
    left_idx = (page - 1) * place_per_page
    right_idx = page * place_per_page
    lat, lng = map(float, location.split(','))

    return render_template('planner.html', js_api_key=api_key, pages_to_display=pages_to_display, location=location, page=page, attractions=session['nearby_search'][left_idx: right_idx], lat=lat, lng=lng)


@app.route('/planner/attractions/add-to-itinerary', methods=['GET', 'POST'])
@login_required
def add_to_itinerary():
    data = request.json
    if 'added' not in session:
        session['added'] = []

    if data['value'] not in session['added']:
        session['added'].append(data['value'])
        message = 'Added to itinerary!'
        return jsonify({'message': message, 'status': 'success'})
    else:
        message = 'Already in itinerary'
        return jsonify({'message': message, 'status': 'danger'})



@app.route('/planner/finalize/', methods=['GET', 'POST'])
@login_required
def finalize():
    if request.method == 'POST':
        mode = request.args.get('mode')
        session['added'] = []

        result = request.form
        itinerary = parse_form(result)

        days = itinerary['date-to'] - itinerary['date-from']
        days = days.days + 1    # for a difference of 1 day, there are 2 days, thus + 1. day 1, day 2
        
        # clean trip data for preparation in database save. add session data required.
        for trip in itinerary['trips']:
            try:
                trip['idx'] = int(trip['idx'])
            except:
                flash('Index error', 'danger')
                return render_template('finalize.html', title=itinerary['itinerary_name'], trips=itinerary['trips'], manual_idx_start=len(itinerary['trips']) , edit_only=True, mode=mode, general_description=itinerary['notes'], date_from=itinerary['date-from'], date_to=itinerary['date-to'])
            
            try:
                trip['day'] = int(trip['day'])
                if trip['day'] > days or trip['day'] < 1:
                    flash('Day number error. Must be less than or equal to total days and greater than 0', 'danger')
                    return render_template('finalize.html', title=itinerary['itinerary_name'], trips=itinerary['trips'], manual_idx_start=len(itinerary['trips']) , edit_only=True, mode=mode, general_description=itinerary['notes'], date_from=itinerary['date-from'], date_to=itinerary['date-to'])
            except:
                flash('Day must be an integer', 'danger')
                return render_template('finalize.html', title=itinerary['itinerary_name'], trips=itinerary['trips'], manual_idx_start=len(itinerary['trips']) , edit_only=True, mode=mode, general_description=itinerary['notes'], date_from=itinerary['date-from'], date_to=itinerary['date-to'])
            
            trip['time-from'], trip['time-to'] = map(lambda x: datetime.strptime(x, "%H:%M").time(), [trip['time-from'], trip['time-to']])
            if trip['time-from'] > trip['time-to']:
                flash("'Time until' is earlier than 'Time from'. Please correct time orders.", 'danger')
                return render_template('finalize.html', title=itinerary['itinerary_name'], trips=itinerary['trips'], manual_idx_start=len(itinerary['trips']) , edit_only=True, mode=mode, general_description=itinerary['notes'], date_from=itinerary['date-from'], date_to=itinerary['date-to'])

            if trip['idx'] == -1:   # manually added trip
                trip['type'] = trip['id']
                continue
            if trip['idx'] == -2:  # no changes in place details in edit 
                continue

            data = session['nearby_search'][trip['idx']]
            trip['lat'], trip['lng'] = data['location'].values()
            trip['google_name'] = data['name']
            trip['vicinity'] = data['vicinity']
            trip['photo_loc'] = data['photo_loc']

        # sort trips. prepare to insert in database
        sorted_trip = sorted(itinerary['trips'], key=lambda x: (x.get('day'), x.get('time-to')))    # try own sorting algorithm later

        # check if dates overlap. if date until of nth trip is later than date beginning of nth+1 trip
        for i in range(len(sorted_trip) - 1):   # to replace. must consider day and time
            if sorted_trip[i]['day'] == sorted_trip[i+1]['day'] and sorted_trip[i]['time-to'] > sorted_trip[i+1]['time-from']:
                flash(f'Time of trips overlap for {sorted_trip[i]['name']} and {sorted_trip[i+1]['name']}', 'danger')
                return render_template('finalize.html', title=itinerary['itinerary_name'], trips=sorted_trip, manual_idx_start=len(sorted_trip) , edit_only=True, mode=mode, general_description=itinerary['notes'], date_from=itinerary['date-from'], date_to=itinerary['date-to'])

        itinerary['trips'] = sorted_trip    # assign sorted_trip to the original dictionary
    
        if mode == 'init':
            # done cleaning and sorting. add to database
            user = Users.query.filter_by(id=session['user_id']).first()
            laag = Trip(user=user, itinerary_name=itinerary['itinerary_name'], itinerary_center=itinerary['location'], notes=itinerary['notes'], date_from=itinerary['date-from'], date_until=itinerary['date-to'])
            db.session.add(laag)

            for trip in itinerary['trips']:
                trip_type = Types.query.filter_by(trip_type=trip['type'].capitalize()).first()
                if not trip_type:
                    trip_type = Types(trip_type=trip['type'].capitalize())
                    db.session.add(trip_type)
                
                destination = None
                if trip['idx'] != -1:
                    destination = Places.query.filter_by(place_id=trip['id']).first()
                    if not destination:
                        destination = Places(place_id=trip['id'], lat=trip['lat'], lng=trip['lng'], name=trip['google_name'], vicinity=trip['vicinity'], photo_loc=trip['photo_loc'])
                        db.session.add(destination)

                save_trip = Itinerary(trip=laag, place=destination, trip_type=trip_type, day=trip['day'], time_from=trip['time-from'], time_until=trip['time-to'], notes=trip['notes'], name=trip['name'])
                db.session.add(save_trip)
            
            db.session.commit()     
            flash('Itinerary saved!', 'success')
            pprint.pprint(itinerary)
            return redirect(url_for('trips'))
        
        elif mode == 'edit':
            if not session.get('trip_id'): 
                session['trip_id'] = request.args.get('trip_id')
            laag = Trip.query.filter_by(id=session['trip_id'], user_id=session['user_id']).first()
            if not laag:
                flash('Error trip does not exist', 'danger')
                return redirect(url_for('finalize', mode='edit', trip_id=session['trip_id']))

            # update trip common details
            laag.itinerary_name = itinerary.get('itinerary_name')
            laag.notes = itinerary.get('notes')
            laag.date_from = itinerary.get('date-from')
            laag.date_until = itinerary.get('date-to')

            # update itineraries
            for trip in itinerary['trips']:
                trip_db = Itinerary.query.filter_by(id=trip['id']).first()
                if trip_db:
                    trip_db.day = trip['day']
                    trip_db.time_from = trip['time-from']
                    trip_db.time_until = trip['time-to']
                    trip_db.notes = trip['notes']
                    trip_db.name = trip['name']
                    continue
                
                # new entry
                trip_type = Types.query.filter_by(trip_type=trip['type'].capitalize()).first()
                if not trip_type:
                    trip_type = Types(trip_type=trip['type'].capitalize())
                    db.session.add(trip_type)

                destination = None
                if trip['idx'] != -1:
                    destination = Places.query.filter_by(place_id=trip['id']).first()
                    if not destination:
                        destination = Places(place_id=trip['id'], lat=trip['lat'], lng=trip['lng'], name=trip['google_name'], vicinity=trip['vicinity'], photo_loc=trip['photo_loc'])
                        db.session.add(destination)
                
                save_trip = Itinerary(trip=laag, place=destination, trip_type=trip_type, day=trip['day'], time_from=trip['time-from'], time_until=trip['time-to'], notes=trip['notes'], name=trip['name'])
                db.session.add(save_trip)
            
            db.session.commit()
            flash('Itinerary updated!', 'success')
            pprint.pprint(itinerary)
            return redirect(url_for('trips'))               
            
        else:
            flash('Request error', 'danger')
            print(request.args)
            return redirect(url_for('index'))

    else:
        mode = request.args.get('mode')
        if mode == 'init':
            if not session.get('title') or not session.get('nearby_search'):
                flash('Fatal error. No place searched', 'danger')
                return redirect(url_for('search'))
            if 'added' not in session:
                flash('Fatal error. Itinerary not initialized', 'danger')
                return redirect(url_for('search'))
            manual_add_idx = len(session['added']) + 1
            
            return render_template('finalize.html', title=session['title'], indices = session['added'], attractions=session['nearby_search'], manual_idx_start = manual_add_idx, mode=mode, edit_only=False, start=0)
        
        elif mode == 'edit':
            if not session.get('trip_id'):
                session['trip_id'] = request.args.get('trip_id')
            attractions = []
            trips = Itinerary.query.filter_by(trip_id=session['trip_id']).all()
            trip_query = Trip.query.filter_by(id=session['trip_id'], user_id=session['user_id']).first()

            for trip in trips:
                data = {}
                data['day'] = trip.day
                data['name'] = trip.name
                data['notes'] = trip.notes
                data['time-from'] = trip.time_from.strftime('%H:%M')
                data['time-to'] = trip.time_until.strftime('%H:%M')
                data['idx'] = -2 if trip.place_id_db else -1     # if place_id_db exists, place was added using api, -2. -1 for manually added places
                data['type'] = Types.query.filter_by(id=trip.type_id).first().trip_type
                data['id'] = trip.id
                attractions.append(data)
            
            sorted_trips = sorted(attractions, key=lambda x:(x['day'], x['time-from']))     # try bubble sort puhon
            
            return render_template('finalize.html', mode='edit', edit_only=True, title=session['title'], date_from=trip_query.date_from, date_to=trip_query.date_until,
                                   general_description=trip_query.notes, manual_idx_start=len(sorted_trips) + len(session['added']), trips=sorted_trips,
                                   attractions=session['nearby_search'], indices=session['added'], start=len(sorted_trips))

        else:
            flash('Request error', 'danger')
            return redirect(url_for('index'))


@app.route('/trips', methods=['GET'])
@login_required
def trips():
    trip = Trip.query.filter_by(user_id=session['user_id']).all()
    data = []

    for place in trip:
        data_dict = {}
        data_dict['id'] = place.id
        data_dict['name'] = place.itinerary_name
        data_dict['date_from'] = place.date_from
        data_dict['date_until'] = place.date_until

        itineraries = Itinerary.query.filter_by(trip_id=place.id).all() # find all itineraries
        photo = None    # in case no photo found
        data_dict['places'] = []

        for itinerary in itineraries:
            data_dict['places'].append(itinerary.name)

        for itinerary in itineraries:
            if itinerary.place_id_db:   # if was found using google api
                photo = Places.query.filter_by(id=itinerary.place_id_db).first()
                if photo:
                    photo = photo.photo_loc
                    break

        data_dict['photo'] = photo
        data.append(data_dict)
            
    return render_template('trips.html', trips=data)


@app.route('/trips/view', methods=['GET', 'POST'])
@login_required
def trip_view():
    if request.method == 'POST':
        action = request.form.get('action')
        trip_id = request.args.get('id')

        trip_query = Trip.query.filter_by(id=trip_id, user_id=session['user_id']).first()
        if not trip_query:
            flash('Trip does not belong to the user. Access failure', 'danger')
            return redirect(url_for('index'))
        
        if action == 'delete':
            clear_session()
            db.session.delete(trip_query)
            db.session.commit()
            flash('Itinerary deleted', 'success')
            return redirect(url_for('trips'))
        
        result = request.form
        indices = ['itinerary_id', 'name', 'notes']
        itr = 0
        notes = []
        data = {}
        for key, value in result.items():
            if key == 'description':
                description = value
                continue
            if key == 'action':
                continue

            if not key.startswith(indices[itr]):
                flash('Data fields error', 'danger')
                return redirect(url_for('trip_view', id=trip_id))
            data[indices[itr]] = value
            itr += 1
            if itr == len(indices):
                notes.append(data)
                data = {}
                itr = 0
                
        trip_query.notes = description

        for data in notes:
            itinerary = Itinerary.query.filter_by(id=data['itinerary_id'], trip_id=trip_id, name=data['name']).first()
            if not itinerary:
                flash('Data fields does not match. Do not tamper source code', 'danger')
                return redirect(url_for('trip_view', id=trip_id))
            itinerary.notes = data['notes']
        
        db.session.commit()

        if action == 'save':            
            flash('Changes successfully saved!', 'success')
            return redirect(url_for('trip_view', id=trip_id))

        elif action == 'edit':
            clear_session()
            session['title'] = trip_query.itinerary_name
            session['location'] = trip_query.itinerary_center
            session['added'] = []
            session['finalize_mode'] = 'edit'
            session['nearby_search'] = nearby_search(session['location'], session['radius'] * 1000)[:session['limit']]

            return redirect(url_for('finalize', mode='edit', trip_id=trip_id))
        
        else:
            flash('Action not found.', 'danger')
            return redirect(url_for('trip_view', id=trip_id))    

    else:
        trip_id = request.args.get('id')
        trip_query = Trip.query.filter_by(id=trip_id, user_id=session['user_id']).first()
        if not trip_query:
            flash('Trip does not belong to user. Access failure.', 'danger')
            return redirect(url_for('index'))
        
        days = trip_query.date_until - trip_query.date_from
        days = days.days + 1
        date_from = trip_query.date_from.strftime('%A %B %d, %Y')
        date_to = trip_query.date_until.strftime('%A %B %d, %Y')
        
        itinerary = [[] for _ in range(days)]
        images = []
        activities = Itinerary.query.filter_by(trip_id=trip_query.id).all()

        for activity in activities:
            day = activity.day
            data = {}

            place_query = Places.query.filter_by(id=activity.place_id_db).first()
            if place_query:
                data['vicinity'] = place_query.vicinity
                images.append((place_query.photo_loc, place_query.name))
            else:
                data['vicinity'] = None

            data['id'] = activity.id
            data['name'] = activity.name
            data['time_from'] = activity.time_from
            data['time_until'] = activity.time_until
            data['notes'] = activity.notes

            itinerary[day - 1].append(data)
        
        final_itinerary = [sorted(sublist, key=lambda x:x.get('time_from')) for sublist in itinerary]
        random.shuffle(images)
        
        return render_template('trip_view.html', trip=trip_query, itinerary=final_itinerary, date_from=date_from, date_to=date_to, images=images, id=trip_id)
    