import configparser
import logging
import logging.handlers
import mysql.connector
import requests
import datetime
import json
import sys

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.handlers.TimedRotatingFileHandler('log/ivao-tracker.log', when="midnight", interval=1, backupCount=10)
handler.setFormatter(logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s', '%Y-%m-%d %H:%M:%S'))
logger.addHandler(handler)
logger.warning('IVAO Tracker Backend has been started.')

config = configparser.ConfigParser()
config.read('ivao-tracker.ini')
logger.info('Config loaded.')

def error_handler(type, value, tb):
    logger.exception(value)
    sys.exit(1)
sys.excepthook = error_handler

'''
    * SQL szerint onlineok legyűjtése tömbbe, mindegyik elem action flag := not_updated
    * whazzup végigiterálása   
        * ha az adott callsign, vid, connected_at, software szerepel már a tömbben, akkor frissítjük, action flag := updated
        * ha nem szerepel még, hozzáadjuk, action flag := created
    * tömb végigiterálása
        * created, updated sorokat updateljük
        * not_updated sorokat disconnecteddel updateljük 
'''

def track():
    logger.info('Let\'s get this tracking started!')
    
    db = mysql.connector.connect(
        host=config['MySQL']['Host'],
        user=config['MySQL']['Username'],
        passwd=config['MySQL']['Password'],
        database=config['MySQL']['Database']    
    )
    cursor = db.cursor(buffered=True, dictionary=True)
    
    
    # legyűjtjük az SQL szerint online klienseket (köztük lehet már nem online is)
    logger.info('Getting ATCs from SQL...')
    cursor.execute('SELECT * FROM atcs WHERE online = 1 ORDER BY callsign')
    atcs = {}
    for atc in cursor.fetchall():
        atc['_action'] = 'not_updated'
        atcs[atc['callsign']] = atc
        
    # meg a pilótákat is
    logger.info('Getting pilots from SQL...')
    cursor.execute('SELECT * FROM pilots WHERE online = 1 ORDER BY callsign')
    pilots = {}
    for pilot in cursor.fetchall():
        pilot['_action'] = 'not_updated'
        pilots[pilot['callsign']] = pilot
    
    
    # legyűjtjük a whazzup szerint online klienseket (ők a biztosan online-ok)
    logger.info('Getting Whazzup feed...')
    r = requests.get(config['Whazzup']['URL'])
    if r.status_code == 200:
        wzstuff = r.json()
        wz_atcs = wzstuff['atcs']
        wz_pilots = wzstuff['pilots']
        
        for wzrow in wz_atcs:
            in_sql = 0
            
            # erre azért van szükség, mert lehetnek a whazzupban broken sorok (software = 2 6 pl.), ezeknél a rating mindig üres. ezek nem kellenek
            if len(wzrow['rating']) > 1:
                # megtalálható-e az SQL-ben egyező VID-del
                if wzrow['callsign'] in atcs:
                    atc = atcs[wzrow['callsign']]
                    
                    if wzrow['vid'] == atc['vid'] and wzrow['connected_at'] == atc['connected_at'].strftime('%Y%m%d%H%M%S') and wzrow['software'] == atc['software']:
                        in_sql = 1
                
                if in_sql:
                    logger.debug('ATC %s is already online in SQL, will be updated.' % (wzrow['callsign']))
                    id = atc['id']
                    atc = wzrow.copy()
                    atc['id'] = id
                    atc['_action'] = 'updated'
                    atcs[wzrow['callsign']] = atc
                else:
                    logger.debug('ATC %s is not in SQL, will be added.' % (wzrow['callsign']))
                    atc = wzrow.copy()
                    atc['_action'] = 'created'
                    atcs[wzrow['callsign']] = atc
                    
                    
        for wzrow in wz_pilots:
            in_sql = 0
            
            # erre azért van szükség, mert lehetnek a whazzupban broken sorok (software = 2 6 pl.), ezeknél a rating mindig üres. ezek nem kellenek
            if len(wzrow['rating']) > 1:
                # megtalálható-e az SQL-ben egyező VID-del
                if wzrow['callsign'] in pilots:
                    pilot = pilots[wzrow['callsign']]
                    
                    if wzrow['vid'] == pilot['vid'] and wzrow['connected_at'] == pilot['connected_at'].strftime('%Y%m%d%H%M%S') and wzrow['software'] == pilot['software']:
                        in_sql = 1
                
                if in_sql:
                    logger.debug('Flight %s is already online in SQL, will be updated.' % (wzrow['callsign']))
                    id = pilot['id']
                    pilot = wzrow.copy()
                    pilot['id'] = id
                    pilot['_action'] = 'updated'
                    pilots[wzrow['callsign']] = pilot
                else:
                    logger.debug('Flight %s is not in SQL, will be added.' % (wzrow['callsign']))
                    pilot = wzrow.copy()
                    pilot['_action'] = 'created'
                    pilots[wzrow['callsign']] = pilot
                
    else:
        logging.error('Status code: %s' % r.status_code)
        
    
    for atc in atcs:
        if atcs[atc]['_action'] == 'not_updated':
            atcs[atc]['_action'] = 'deleted'
            logger.debug('ATC %s is not in Whazzup, will be deleted.' % (atc))
            
        if atcs[atc]['_action'] == 'updated':
            a = atcs[atc]
            cursor.execute('UPDATE atcs SET latitude = %s, longitude = %s, frequency = %s, radar_range = %s, atis = %s, atis_time = %s, last_tracked_at = NOW() WHERE id = %s', (
                a['latitude'],
                a['longitude'],
                a['frequency'],
                a['radar_range'],
                a['atis'],
                a['atis_time'],
                a['id'],
            ))
            logger.debug('ATC %s has been updated in SQL.' % (atc))
        
        if atcs[atc]['_action'] == 'created':
            a = atcs[atc]
            cursor.execute('INSERT INTO atcs (callsign, vid, status, rating, latitude, longitude, server, protocol, software, frequency, radar_range, atis, atis_time, online, connected_at, last_tracked_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, NOW())', (
                a['callsign'],
                a['vid'],
                a['status'],
                a['rating'],
                a['latitude'],
                a['longitude'],
                a['server'],
                a['protocol'],
                a['software'],
                a['frequency'],
                a['radar_range'],
                a['atis'],
                a['atis_time'],
                a['connected_at'],
            ))
            logger.debug('ATC %s has been added to SQL.' % (atc))
            
        if atcs[atc]['_action'] == 'deleted':
            a = atcs[atc]
            cursor.execute('UPDATE atcs SET online = 0, disconnected_at = NOW() WHERE id = %s', (a['id'], ))
            logger.debug('ATC %s has been deleted from SQL.' % (atc))
    
    
    for pilot in pilots:
        if pilots[pilot]['_action'] == 'not_updated':
            pilots[pilot]['_action'] = 'deleted'
            logger.debug('Flight %s is not in Whazzup, will be deleted.' % (pilot))
            
        if pilots[pilot]['_action'] == 'updated':
            a = pilots[pilot]
            cursor.execute('UPDATE pilots SET latitude = %s, longitude = %s, heading = %s, on_ground = %s, altitude = %s, groundspeed = %s, mode_a = %s, fp_aircraft = %s, fp_speed = %s, fp_rfl = %s, fp_departure = %s, fp_destination = %s, fp_alternate = %s, fp_alternate2 = %s, fp_type = %s, fp_pob = %s, fp_route = %s, fp_item18 = %s, fp_rev = %s, fp_rule = %s, fp_deptime = %s, fp_eet = %s, fp_endurance = %s, last_tracked_at = NOW() WHERE id = %s', (
                a['latitude'],
                a['longitude'],
                a['heading'],
                a['on_ground'],
                a['altitude'],
                a['groundspeed'],
                a['mode_a'],
                a['fp_aircraft'],
                a['fp_speed'],
                a['fp_rfl'],
                a['fp_departure'],
                a['fp_destination'],
                a['fp_alternate'],
                a['fp_alternate2'],
                a['fp_type'],
                a['fp_pob'],
                a['fp_route'],
                a['fp_item18'],
                a['fp_rev'],
                a['fp_rule'],
                a['fp_deptime'],
                a['fp_eet'],
                a['fp_endurance'],
                a['id'],
            ))
            logger.debug('Flight %s has been updated in SQL.' % (pilot))
        
        if pilots[pilot]['_action'] == 'created':
            a = pilots[pilot]
            cursor.execute('INSERT INTO pilots (callsign, vid, status, rating, latitude, longitude, server, protocol, software, heading, on_ground, altitude, groundspeed, mode_a, fp_aircraft, fp_speed, fp_rfl, fp_departure, fp_destination, fp_alternate, fp_alternate2, fp_type, fp_pob, fp_route, fp_item18, fp_rev, fp_rule, fp_deptime, fp_eet, fp_endurance, sim_type, online, connected_at, last_tracked_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, NOW())', (
                a['callsign'],
                a['vid'],
                a['status'],
                a['rating'],
                a['latitude'],
                a['longitude'],
                a['server'],
                a['protocol'],
                a['software'],
                a['heading'],
                a['on_ground'],
                a['altitude'],
                a['groundspeed'],
                a['mode_a'],
                a['fp_aircraft'],
                a['fp_speed'],
                a['fp_rfl'],
                a['fp_departure'],
                a['fp_destination'],
                a['fp_alternate'],
                a['fp_alternate2'],
                a['fp_type'],
                a['fp_pob'],
                a['fp_route'],
                a['fp_item18'],
                a['fp_rev'],
                a['fp_rule'],
                a['fp_deptime'],
                a['fp_eet'],
                a['fp_endurance'],
                a['sim_type'],
                a['connected_at'],
            ))
            logger.debug('Flight %s has been added to SQL.' % (pilot))
            
        if pilots[pilot]['_action'] == 'deleted':
            a = pilots[pilot]
            cursor.execute('UPDATE pilots SET online = 0, disconnected_at = NOW() WHERE id = %s', (a['id'], ))
            logger.debug('Flight %s has been deleted from SQL.' % (pilot))
            
    db.commit()
    logger.info('Tracking is done, DB has been committed.')


track()

    