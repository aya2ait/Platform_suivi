import os

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:@localhost/ONEE_SuiviDeplacements")
IOT_HUB_CONNECTION_STRING = "HostName=myapp.azure-devices.net;DeviceId=mydvice;SharedAccessKey=cNgslTZVdJ4hdClC2FqSbWVJKCtgGSih6YryGG8tzR8="

# Geographic bounds for Morocco
MOROCCO_BOUNDS = {
    'min_lat': 27.6,
    'max_lat': 35.9,
    'min_lon': -13.2,
    'max_lon': -1.0
}

# Major cities in Morocco with their coordinates
MAJOR_CITIES = {
    'Casablanca': (33.5731, -7.5898),
    'Rabat': (34.0209, -6.8416),
    'Marrakech': (31.6295, -7.9811),
    'Fès': (34.0181, -5.0078),
    'Tanger': (35.7595, -5.8340),
    'Agadir': (30.4278, -9.5981),
    'Meknès': (33.8935, -5.5473),
    'Oujda': (34.6814, -1.9086),
    'Kénitra': (34.2610, -6.5802),
    'Tétouan': (35.5889, -5.3626)
}