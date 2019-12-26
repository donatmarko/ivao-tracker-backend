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
'''
def error_handler(type, value, tb):
    logger.exception(value)
    sys.exit(1)
sys.excepthook = error_handler'''

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
    atcs = []
    for atc in cursor.fetchall():
        atc['_action'] = 'not_updated'
        atcs.append(atc)
        
    # meg a pilótákat is
    logger.info('Getting pilots from SQL...')
    cursor.execute('SELECT * FROM pilots WHERE online = 1 ORDER BY callsign')
    pilots = []
    for pilot in cursor.fetchall():
        pilot['_action'] = 'not_updated'
        pilots.append(pilot)
    
    
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
                # megkeressük a tömbben az azonos callsignnal rendelkező sort
                idx = next((index for (index, d) in enumerate(atcs) if d["callsign"] == wzrow['callsign']), -1)
                
                if idx > -1:
                    if wzrow['vid'] == atcs[idx]['vid'] and wzrow['connected_at'] == atcs[idx]['connected_at'].strftime('%Y%m%d%H%M%S') and wzrow['software'] == atcs[idx]['software']:
                        in_sql = 1
                
                if in_sql:
                    logger.debug('ATC %s is already online in SQL, will be updated.' % (wzrow['callsign']))
                    id = atcs[idx]['id']
                    atc = wzrow.copy()
                    atc['id'] = id
                    atc['_action'] = 'updated'
                    atcs[idx] = atc
                else:
                    logger.debug('ATC %s is not in SQL, will be added.' % (wzrow['callsign']))
                    atc = wzrow.copy()
                    atc['_action'] = 'created'
                    atcs.append(atc)
            else:
                logger.warning('Broken whazzup line (%s) found, skipping.' % (wzrow['callsign']))
                    
                    
        for wzrow in wz_pilots:
            in_sql = 0
            
            # erre azért van szükség, mert lehetnek a whazzupban broken sorok (software = 2 6 pl.), ezeknél a rating mindig üres. ezek nem kellenek
            if len(wzrow['rating']) > 1:           
                # megkeressük a tömbben az azonos callsignnal rendelkező sort
                idx = next((index for (index, d) in enumerate(pilots) if d["callsign"] == wzrow['callsign']), -1)
                
                if idx > -1:
                    if wzrow['vid'] == pilots[idx]['vid'] and wzrow['connected_at'] == pilots[idx]['connected_at'].strftime('%Y%m%d%H%M%S') and wzrow['software'] == pilots[idx]['software']:
                        in_sql = 1
                
                if in_sql:
                    logger.debug('Flight %s is already online in SQL, will be updated.' % (wzrow['callsign']))
                    id = pilots[idx]['id']
                    pilot = wzrow.copy()
                    pilot['id'] = id
                    pilot['_action'] = 'updated'
                    pilots[idx] = pilot
                else:
                    logger.debug('Flight %s is not in SQL, will be added.' % (wzrow['callsign']))
                    pilot = wzrow.copy()
                    pilot['_action'] = 'created'
                    pilots.append(pilot)
            else:
                logger.warning('Broken whazzup line (%s) found, skipping.' % (wzrow['callsign']))
                
    else:
        logging.error('Status code: %s' % r.status_code)
        
    
    atc_created = 0
    atc_updated = 0
    atc_deleted = 0
    for atc in atcs:
        if atc['_action'] == 'updated':
            cursor.execute('UPDATE atcs SET latitude = %s, longitude = %s, frequency = %s, radar_range = %s, atis = %s, atis_time = %s, last_tracked_at = NOW() WHERE id = %s', (
                atc['latitude'],
                atc['longitude'],
                atc['frequency'],
                atc['radar_range'],
                atc['atis'],
                atc['atis_time'],
                atc['id'],
            ))
            logger.debug('ATC session #%s (%s) has been updated in SQL.' % (atc['id'], atc['callsign']))
            atc_updated += 1
        
        if atc['_action'] == 'created':
            cursor.execute('INSERT INTO atcs (callsign, vid, status, rating, latitude, longitude, server, protocol, software, frequency, radar_range, atis, atis_time, online, connected_at, last_tracked_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, NOW())', (
                atc['callsign'],
                atc['vid'],
                atc['status'],
                atc['rating'],
                atc['latitude'],
                atc['longitude'],
                atc['server'],
                atc['protocol'],
                atc['software'],
                atc['frequency'],
                atc['radar_range'],
                atc['atis'],
                atc['atis_time'],
                atc['connected_at'],
            ))
            logger.debug('New ATC session (%s) has been added to SQL.' % (atc['callsign']))
            atc_created += 1
            
        if atc['_action'] == 'not_updated':
            cursor.execute('UPDATE atcs SET online = 0, disconnected_at = NOW() WHERE id = %s', (atc['id'], ))
            logger.debug('ATC session #%s (%s) has been deleted from SQL.' % (atc['id'], atc['callsign']))
            atc_deleted += 1
    
    
    pilot_created = 0
    pilot_updated = 0
    pilot_deleted = 0
    for pilot in pilots:
        if pilot['_action'] == 'updated':
            cursor.execute('UPDATE pilots SET latitude = %s, longitude = %s, heading = %s, on_ground = %s, altitude = %s, groundspeed = %s, mode_a = %s, fp_aircraft = %s, fp_speed = %s, fp_rfl = %s, fp_departure = %s, fp_destination = %s, fp_alternate = %s, fp_alternate2 = %s, fp_type = %s, fp_pob = %s, fp_route = %s, fp_item18 = %s, fp_rev = %s, fp_rule = %s, fp_deptime = %s, fp_eet = %s, fp_endurance = %s, last_tracked_at = NOW() WHERE id = %s', (
                pilot['latitude'],
                pilot['longitude'],
                pilot['heading'],
                pilot['on_ground'],
                pilot['altitude'],
                pilot['groundspeed'],
                pilot['mode_a'],
                pilot['fp_aircraft'],
                pilot['fp_speed'],
                pilot['fp_rfl'],
                pilot['fp_departure'],
                pilot['fp_destination'],
                pilot['fp_alternate'],
                pilot['fp_alternate2'],
                pilot['fp_type'],
                pilot['fp_pob'],
                pilot['fp_route'],
                pilot['fp_item18'],
                pilot['fp_rev'],
                pilot['fp_rule'],
                pilot['fp_deptime'],
                pilot['fp_eet'],
                pilot['fp_endurance'],
                pilot['id'],
            ))
            logger.debug('Flight session #%s (%s) has been updated in SQL.' % (pilot['id'], pilot['callsign']))
            pilot_updated += 1
        
        if pilot['_action'] == 'created':
            a = pilot
            cursor.execute('INSERT INTO pilots (callsign, vid, status, rating, latitude, longitude, server, protocol, software, heading, on_ground, altitude, groundspeed, mode_a, fp_aircraft, fp_speed, fp_rfl, fp_departure, fp_destination, fp_alternate, fp_alternate2, fp_type, fp_pob, fp_route, fp_item18, fp_rev, fp_rule, fp_deptime, fp_eet, fp_endurance, sim_type, online, connected_at, last_tracked_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, NOW())', (
                pilot['callsign'],
                pilot['vid'],
                pilot['status'],
                pilot['rating'],
                pilot['latitude'],
                pilot['longitude'],
                pilot['server'],
                pilot['protocol'],
                pilot['software'],
                pilot['heading'],
                pilot['on_ground'],
                pilot['altitude'],
                pilot['groundspeed'],
                pilot['mode_a'],
                pilot['fp_aircraft'],
                pilot['fp_speed'],
                pilot['fp_rfl'],
                pilot['fp_departure'],
                pilot['fp_destination'],
                pilot['fp_alternate'],
                pilot['fp_alternate2'],
                pilot['fp_type'],
                pilot['fp_pob'],
                pilot['fp_route'],
                pilot['fp_item18'],
                pilot['fp_rev'],
                pilot['fp_rule'],
                pilot['fp_deptime'],
                pilot['fp_eet'],
                pilot['fp_endurance'],
                pilot['sim_type'],
                pilot['connected_at'],
            ))
            logger.debug('New flight session (%s) has been added to SQL.' % (pilot['callsign']))
            pilot_created += 1
            
        if pilot['_action'] == 'not_updated':
            cursor.execute('UPDATE pilots SET online = 0, disconnected_at = NOW() WHERE id = %s', (pilot['id'], ))
            logger.debug('Flight session #%s (%s) has been deleted from SQL.' % (pilot['id'], pilot['callsign']))
            pilot_deleted += 1
           
    db.commit()
    cursor.close()
    db.close()
    logger.info('Tracking is done, DB has been committed.')
    logger.info('ATC statistics: %s created, %s updated, %s deleted. Currently %s online.' % (atc_created, atc_updated, atc_deleted, (atc_created + atc_updated)))
    logger.info('Pilot statistics: %s created, %s updated, %s deleted. Currently %s online.' % (pilot_created, pilot_updated, pilot_deleted, (pilot_created + pilot_updated)))


track()

    