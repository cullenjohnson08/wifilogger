import os.path
import socket
import sys
import os
import sqlite3
from subprocess import call
from wifi import Cell
from pynmea import nmea
import time
import serial
import logging
import picamera
import fractions
import pdb

def getlocation(gpsdevice): #Pass in gps interface
    #Get current location and return it as a key pair
    ser = serial.Serial()
    ser.port = gpsdevice
    ser.baudrate = 9600 
    print("In GPS Getlocation")
    try:
        ser.open()
        logging.debug("Getting GPS Location")
        gotlocation = False
        while (gotlocation == False):
            gpstext = str(ser.readline())
            if (gpstext[3:8] == 'GPGGA'):
                #Found the proper string, now get the lat long
                #Probably needs a check for GPS lock.
                print("Got GPGGA")
                gotlocation = True
                g = nmea.GPGGA()
                #print(gpstext) 
                g.parse(gpstext)
                gpsdata = {'latitude':g.latitude, 'longitude': g.longitude, 'timestamp':g.timestamp, 'altitude':g.antenna_altitude}
            else:
                #print("bad string")
                #print("GPS Text was: " + gpstext[3:8])
                #print("Fulltext as: " + gpstext)
	#if gpsdata['latitude'] == '' or gpsdata['longitude'] == '' or gpsdata['altitude'] == '' or gpsdata['timestamp'] == '':
                #gpsdata = {'latitude':'0', 'longitude': '0', 'timestamp':'0', 'altitude':'0'}
    except:
        print("GPS Not found")
        logging.debug("GPS Not found.  ")
        gpsdata = {'latitude':'0', 'longitude': '0', 'timestamp':'0', 'altitude':'0'}
    return gpsdata


def initdb(dbname):
    #Check if db exists.  Create the db if it does not.
    if os.path.isfile(dbname + ".db"):
        conn = sqlite3.connect(dbname + ".db")
        print ("Connected to " + dbname)
        return conn
    else:
        #Open and create the database and add encoding types
        conn = sqlite3.connect(dbname + ".db")
        c = conn.cursor()
        c.execute('''CREATE TABLE datasamples
            (bssid character(12), essid varchar(255),
            power int, channel int, enc_type varchar(100), mode varchar(100), pic_filename varchar(100), latitude float, longitude float, altitude float, temperature int, created_at float)''')
        conn.commit()
        print ("Database Created")
        return conn


def saveData(wifitree, gpsdata, picnum, conn, temp):
        for ap in wifitree:
                encryption = ap.encryption_type
                print("bssid: " + ap.ssid)
                print(gpsdata)
                picfilename = ("cap" + str(picnum) +".jpg")
                #TODO: Take picture with superimposed GPS coordinates
                #Save to database
                c = conn.cursor()
                c.execute("INSERT INTO datasamples(bssid, essid, power, channel, enc_type, mode, pic_filename, latitude, longitude, altitude, temperature, created_at) VALUES('" + ap.address + "','" + ap.ssid + "','" + str(ap.signal) + "','" + str(ap.channel) + "','" + encryption + "','" + ap.mode + "', '" + picfilename + "','" + str(float(gpsdata['latitude'])) + "','" + str(float(gpsdata['longitude'])) + "', '" + str(float(gpsdata['altitude'])) + "', '" + str(temp) + "', '" + str(float(gpsdata['timestamp'])) + "')")
                conn.commit()

def scan(interface):
    print("Begin scan")
    wifitree = Cell.all(interface)
    print(wifitree)
    return wifitree

def converter(num):
        if len(num) == 11:
            num = num[1:10]
        #import pdb;pdb.set_trace()
        num1 = float(num)
        mod1 = num1%100
        deg = int((num1-mod1)/100)
        mod2 = mod1%1
        min = int(mod1-mod2)
        sec = int(((round(mod2, 4)/60)*3600)*100)
        return str(deg) + '/1,' + str(min) + '/1,' + str(sec) + '/100'
        

def main(argv):
    #get wifi device from argv
    print ("Arg: " )
    print (argv)
    if (len(argv) == 3):
        interface = argv[1]
        gpsdevice = argv[2]
    else:
        interface = 'wlan0'
        gpsdevice = '/dev/ttyAMA0'
    camera = picamera.PiCamera()

    #Main Loop
    picnum = 0
    while (os.path.isfile("cap" +str(picnum)+".jpg") == True):
        picnum += 1 
    conn = initdb("balloonsat")
    while (1):
        gpsdata = getlocation(gpsdevice)
        imagefile = ("cap" + str(picnum) + ".jpg")
        try:
            print("long: "+str(gpsdata['longitude']))
            long = converter(gpsdata['longitude'])
            lat = converter(gpsdata['latitude'])
            alt = str(int(float(gpsdata['altitude']))) + '/1'
        except:
            print("Gps Data could not be converted")
        try:
            tempfile = open("/sys/class/thermal/thermal_zone0/temp")
            tempInt = int(tempfile.read(6))
        except:
            tempInt = 0
            print("Temp data could not be retrieved")
        try:
            wifitree = scan(interface)
            print (wifitree)
        except:
            print("No wifi data recieved")
        try:
            print("Going to send: " + lat + " Lat and " +long + " Long")
            camera.exif_tags['GPS.GPSAltitude'] = alt
            camera.exif_tags['GPS.GPSAltitudeRef'] = '0'
            camera.exif_tags['GPS.GPSLatitude'] = lat
            camera.exif_tags['GPS.GPSLatitudeRef'] = 'N'
            camera.exif_tags['GPS.GPSLongitude'] = long
            camera.exif_tags['GPS.GPSLongitudeRef'] = 'W'
            #camera.exif_tags[0x9400] = str(tempInt) + '/1000'
            camera.capture(imagefile)
        except:
            print("No camera currently detected")
        try: 
            saveData(wifitree, gpsdata, picnum, conn, tempInt)
        except:
            print("No wifi adapter detected")
        picnum = picnum + 1
        time.sleep(10) #wait 10 seconds, then rescan


if __name__ == "__main__":
    main(sys.argv)
