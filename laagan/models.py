from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)   
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    home_add = db.Column(db.String(100), nullable=True)

    settings = db.relationship('Setting', back_populates='user', cascade='all, delete-orphan', passive_deletes=True)
    trips = db.relationship('Trip', back_populates='user', cascade='all, delete-orphan', passive_deletes=True)

    def __repr__(self):
        return str(
            {
                'id': self.id,
                'username': self.username,
                'password': self.password,
                'email': self.email,
                'home_address': self.home_add
            }
        )


class Setting(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    radius = db.Column(db.Float, default=100.0)
    nearby_search_limit = db.Column(db.Integer, default=50)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    user = db.relationship('Users', back_populates='settings')

    def __repr__(self):
        return str(
            {
                'setting_id': self.id,
                'radius': self.radius,
                'nearby_search_limit': self.nearby_search_limit,
                'user_id': self.user_id
            }
        )


class Trip(db.Model):
    __tablename__ = 'trips'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    itinerary_name = db.Column(db.String(255), nullable=False)
    itinerary_center = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.String(1023), nullable=True)
    date_from = db.Column(db.Date, nullable=False)
    date_until = db.Column(db.Date, nullable=False)

    user = db.relationship('Users', back_populates='trips')
    itinerary = db.relationship('Itinerary', back_populates='trip', cascade='all, delete-orphan', passive_deletes=True)

    def __repr__(self):
        return str(
            {
                'trip_id': self.id,
                'user_id': self.user_id,
                'itinerary_name': self.itinerary_name,
                'notes': self.notes,
                'date_from': self.date_from,
                'date_until': self.date_until,
                'center': self.itinerary_center
            }
        )
    

class Places(db.Model):
    __tablename__ = 'places'
    id = db.Column(db.Integer, primary_key=True)
    place_id = db.Column(db.String(255), nullable=False)   
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    name = db.Column(db.String(255), nullable=False)    # from google api
    vicinity = db.Column(db.String(255), nullable=False)
    photo_loc = db.Column(db.String(255), nullable=True)

    itinerary = db.relationship('Itinerary', back_populates='place', cascade='all, delete-orphan', passive_deletes=True)

    def __repr__(self):
        return str(
            {
                'id': self.id,
                'place_id': self.place_id,
                'lat': self.lat,
                'lng': self.lng,
                'name': self.name,
                'vicinity': self.vicinity,
                'photo_loc': self.photo_loc
            }
        )

    
class Itinerary(db.Model):
    __tablename__ = 'itinerary'
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id', ondelete='CASCADE'), nullable=False)
    place_id_db = db.Column(db.Integer, db.ForeignKey('places.id', ondelete='CASCADE'), nullable=True)
    type_id = db.Column(db.Integer, db.ForeignKey('types.id', ondelete='CASCADE'), nullable=False)
    day = db.Column(db.Integer, nullable=False)
    time_from = db.Column(db.Time, nullable=False)
    time_until = db.Column(db.Time, nullable=False)
    notes = db.Column(db.String(1023), nullable=True)
    name = db.Column(db.String(255), nullable=False)

    trip = db.relationship('Trip', back_populates='itinerary')
    place = db.relationship('Places', back_populates='itinerary')
    trip_type = db.relationship('Types', back_populates='itinerary')

    def __repr__(self):
        return str(
            {
                'itinerary_id': self.id,
                'trip_id': self.trip_id,
                'place_id': self.place_id_db,
                'type_id': self.type_id,
                'day': self.day,
                'time_from': self.time_from,
                'time_until': self.time_until,
                'notes': self.notes,
                'name': self.name
            }
        )
    
class Types(db.Model):
    __tablename__ = 'types'
    id = db.Column(db.Integer, primary_key=True)
    trip_type = db.Column(db.String(255), nullable=False)

    itinerary = db.relationship('Itinerary', back_populates='trip_type')

    def __repr__(self):
        return str(
            {
                'id': self.id,
                'type': self.trip_type
            }
        )