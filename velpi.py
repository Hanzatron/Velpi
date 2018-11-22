#!/usr/bin/python

#####################################################################################
# Velbuslog.py																	HANS
# V1.0
#
# V0.0		02/09/16		created
# V1.0		09/09/16		Test met flask server
#####################################################################################
# Test Velbus uitlezen via USB en printen naar terminal met timestamp
# 
# Tip om naam USB device te weten te komen:
# sudo dmesg -C (kernel log leegmaken)
# USB device insteken
# sudo dmesg uitvoeren en zien wat er in de log is bijgekomen
#
# sudo apt-get install python-mysqldb
#####################################################################################
#!/usr/bin/python
import serial
import binascii

import time
import datetime
#~ from datetime import datetime

import os

from threading import Thread

from flask import Flask
from flask import request
from flask import render_template
from flask import redirect

import smtplib #voor email zenden
import textwrap #voor email zenden

import poplib #voor email lezen
from email import parser #voor email lezen
from email.mime.text import MIMEText


#~ import plotly.plotly as py
#~ from plotly.graph_objs import Scatter, Layout, Figure
#~ import json # used to parse config.json

import MySQLdb

import soco

relais = []
blinds = []
thermostats = []
pirs = []
sonoszones =[]
events = [] #{timestamp : 
#now = datetime.datetime.now()

class Velbusconnection(object):
	def __init__(self):
		self.sleep_after_write = 0.5
		self.mess = []
		self.messstring = ""
		self.write_message = ""
		
		self.printmessage = False
		self.logmessage = False
		self.maildeurbel = True
		self.templogging = True
		
		try:
			self.serial = serial.Serial('/dev/ttyACM0')
			self.serial.baud_rate = 38400
			self.serial.byte_size = serial.EIGHTBITS
			self.serial.parity = serial.PARITY_NONE
			self.serial.stopbits = serial.STOPBITS_ONE
			self.serial.xonxoff = 0
			self.serial.RTSCTS = 1
		except serial.serialutil.SerialException:
			print"Geen connectie met USB"
			

	def read_data(self):
		#~ try:
			now = datetime.datetime.now()
			self.mess = []
			count = 0
			while count < 4:
				data = self.serial.read(1) #1 byte uitlezen
				self.mess.append (str(binascii.hexlify(data))) #binaire data omzetten in hexadecimaal
				count = count +1
			count = 0
			if (int(self.mess[3],16) <= 8): #controle of dit bericht wel kan kloppen, eventueel checksum test doen of test op aanwezigheid "fb" of "f8"!
				
				while count < int(self.mess[3]):
					data = self.serial.read(1)
					self.mess.append (binascii.hexlify(data)) #bij in python list zetten
					count = count +1
				count = 0
				while count < 2:
					data = self.serial.read(1)
					self.mess.append (binascii.hexlify(data))
					count = count +1
			
				self.messstring = str(datetime.datetime.now()) + " --- "
				for i in self.mess:
					self.messstring = self.messstring + i + " "
					
								
				#THERMOSTAT STATUS ONTVANGEN EN IN THERMOSTATOBJECT ZETTEN
				if (self.mess[1] == 'fb') and (self.mess[3] == '08') and (self.mess[4] == 'ea'):
					for thermostat in thermostats:
						if thermostat.adres == str(self.mess[2]): #als het adres van message overeenkomt met het adres van de thermostat
							thermostat.status_message(self.mess)								
								
		
				#TEMPERATUURLOGGING
				if (self.mess[1] == 'fb') and (self.mess[4] == 'e6'):
					
					for thermostat in thermostats:
						if thermostat.adres == str(self.mess[2]):
							thermostat.temperatuur = ((int(self.mess[5],16))/2.0)
					
					if (self.templogging == True):
						SQLlog_temp(str(self.mess[2]),(float(int(self.mess[5],16))/2.0))
				#~ if (self.templogging == True) and (self.mess[1] == 'fb') and (self.mess[4] == 'e6') and (self.mess[2] == '14'):
					#~ Plotly_temp((float(int(self.mess[5],16))/2.0))
					
				#PRINT MESSAGE OP CONSOLE
				if self.printmessage:
					print self.messstring
				
				#SQL LOGGING:
				if self.logmessage:
					log_message(self.mess)
				
				#DEURBEL:
				if (str(self.mess[2]) == "04") and (str(self.mess[4]) == "00") and (str(self.mess[5]) == "01") and (self.maildeurbel): 
					#~ zend_email('smtp.telenet.be','isengard68@telenet.be',['hans_van_gaveren@hotmail.com'],"deurbel!","Verzonden door Isengard op " + str(datetime.datetime.now()))
					zend_email('hans_van_gaveren@hotmail.com', 'Deurbel!','Verzonden door Isengard op ' + str(datetime.datetime.now()))
				
				#ALS MESSAGE VAN PIR KOMT, NAAR JUISTE PIR STUREN
				for pir in pirs:
					if pir.adres == str(self.mess[2]):
						pir.lees_message(self.mess)
				
				#ALS MESSAGE VAN RELAIS KOMT, NAAR JUISTE RELAIS STUREN
				for relaisblok in relais:
					if relaisblok.adres == str(self.mess[2]):
						relaisblok.lees_message(self.mess)
					#~ if relaisblok.adres == "05" and relaisblok.channelstatus[5] == True:
						
						
				#ALS MESSAGE VAN BLIND KOMT, NAAR JUISTE BLIND STUREN
				for blind in blinds:
					if blind.adres == str(self.mess[2]):
						blind.lees_message(self.mess)
						

			else:
				print "Fout bericht ontvangen!"
				print self.mess[1]
		#~ except:
			#~ print "read_data error at " + str(datetime.datetime.now())
			#~ self.mess = []
			#~ count = 0
			#~ time.sleep(1)
			#~ self.serial.close()
						
	def write_data(self):
		try:
			if self.write_message <> "":
				self.serial.write(binascii.unhexlify(self.write_message))
				#~ print str(datetime.datetime.now()) + " --- " + "write command " + str(self.write_message)
				#~ time.sleep(self.sleep_after_write)
				self.write_message = ""
				
			for rel in relais:
				if rel.message_to_velbus <> "":
					self.serial.write(binascii.unhexlify(rel.message_to_velbus))
					#~ print str(datetime.datetime.now()) + " --- " + "write command " + str(rel.message_to_velbus)
					#~ time.sleep(self.sleep_after_write)
					rel.message_to_velbus = ""
					break
					
			for blind in blinds:
				if blind.message_to_velbus <> "":
					self.serial.write(binascii.unhexlify(blind.message_to_velbus))
					#~ print str(datetime.datetime.now()) + " --- " + "write command " + str(blind.message_to_velbus)
					#~ time.sleep(self.sleep_after_write)
					blind.message_to_velbus = ""
					break
					
			for thermostat in thermostats:
				if thermostat.message_to_velbus <> "":
					self.serial.write(binascii.unhexlify(thermostat.message_to_velbus))
					#~ print str(datetime.datetime.now()) + " --- " + "write command " + str(thermostat.message_to_velbus)
					#~ time.sleep(self.sleep_after_write)
					thermostat.message_to_velbus = ""
					break
					
			for pir in pirs:
				if pir.message_to_velbus <> "":
					self.serial.write(binascii.unhexlify(pir.message_to_velbus))
					#~ print str(datetime.datetime.now()) + " --- " + "write command " + str(thermostat.message_to_velbus)
					#~ time.sleep(self.sleep_after_write)
					pir.message_to_velbus = ""
					break
		
			time.sleep(0.1)
			
		except:
			print "write_data error at " + str(datetime.datetime.now())
			self.write_message = ""
			time.sleep(1)
			self.serial.close()

class Thermostat(object):
	'Behandelt thermostaatfunctie in OLED panel of gewoon glasspanel'
	def __init__(self, adres):
		self.adres = adres
		self.message_to_velbus = ""
		self.mode = 0 # 0=disable; 1=comfort; 2=dag; 3=nacht: 4=antivries; 5=manueel; 6=timer
		self.mode_str = "Disable"
		self.pompaanvraag = False
		self.zoneaanvraag = False
		self.boost = False
		self.alarm1 = False
		self.alarm2 = False
		self.alarm3 = False
		self.alarm4 = False
		self.temperatuur =0.0
		self.sp = 0.0
		self.sp_dag = 0.0
		self.sp_nacht = 0.0
		self.sp_comfort = 0.0
		
		self.naam = ""

	def req_status(self):
		mess = []
		mess.append("0f") #start bericht
		mess.append("fb") #low priority
		mess.append(str(self.adres)) #adres van module
		mess.append("02") #aantal byte
		mess.append("fa")
		mess.append ("00") #don't care
		mess = ad_checksum(mess)				
		self.message_to_velbus = ""
		for byte in mess:
			self.message_to_velbus = self.message_to_velbus + byte
			
	def sleeptimer_comfort(self, minuten):
		#thermostat gedurende x seconden in comfortmodus zetten
		mess = []
		mess.append("0f") #start bericht
		mess.append("fb") #low priority
		mess.append(str(self.adres)) #adres van module
		mess.append("03") #aantal byte
		mess.append("db") #COMMAND_SWITCH_TO_COMFORT_MODE
		mess.append (uur_to_sec(0,0,minuten)[1]) #high byte sleep time
		mess.append (uur_to_sec(0,0,minuten)[0]) #low byte sleep time
		mess = ad_checksum(mess)				
		self.message_to_velbus = ""
		for byte in mess:
			self.message_to_velbus = self.message_to_velbus + byte
			
	def sleeptimer_dag(self, minuten):
		#thermostat gedurende x seconden in dagmodus zetten
		#bij 65280 minuten (H'FF00) wordt de modus veranderd naar dag zonder sleeptimer
		#bij 65535 minuten wordt de thermostaat manueel gezet
		mess = []
		mess.append("0f") #start bericht
		mess.append("fb") #low priority
		mess.append(str(self.adres)) #adres van module
		mess.append("03") #aantal byte
		mess.append("dc") #COMMAND_SWITCH_TO_DAY_MODE
		mess.append (uur_to_sec(0,0,minuten)[1]) #high byte sleep time
		mess.append (uur_to_sec(0,0,minuten)[0]) #low byte sleep time
		mess = ad_checksum(mess)				
		self.message_to_velbus = ""
		for byte in mess:
			self.message_to_velbus = self.message_to_velbus + byte
			
	def sleeptimer_nacht(self, minuten):
		#thermostat gedurende x seconden in nachtmodus zetten
		mess = []
		mess.append("0f") #start bericht
		mess.append("fb") #low priority
		mess.append(str(self.adres)) #adres van module
		mess.append("03") #aantal byte
		mess.append("dd") #COMMAND_SWITCH_TO_NIGHT_MODE
		mess.append (uur_to_sec(0,0,minuten)[1]) #high byte sleep time
		mess.append (uur_to_sec(0,0,minuten)[0]) #low byte sleep time
		mess = ad_checksum(mess)				
		self.message_to_velbus = ""
		for byte in mess:
			self.message_to_velbus = self.message_to_velbus + byte
			
	def sleeptimer_antivries(self, minuten):
		#thermostat gedurende x seconden in antivriesmodus zetten
		mess = []
		mess.append("0f") #start bericht
		mess.append("fb") #low priority
		mess.append(str(self.adres)) #adres van module
		mess.append("03") #aantal byte
		mess.append("de") #COMMAND_SWITCH_TO_SAFE_MODE
		mess.append (uur_to_sec(0,0,minuten)[1]) #high byte sleep time
		mess.append (uur_to_sec(0,0,minuten)[0]) #low byte sleep time
		mess = ad_checksum(mess)				
		self.message_to_velbus = ""
		for byte in mess:
			self.message_to_velbus = self.message_to_velbus + byte
	
	def status_message(self, message):
		#THERMOSTAT MODE BEPALEN UIT DATABYTE2
		message[5] = "999" + message[5]
		if (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-6]) == "1":
			self.mode = 2 #dag modus
			self.mode_str = "dagmodus"
		elif (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-7]) == "1":
			self.mode = 1 #comfort modus
			self.mode_str = "comfortmodus"
		elif (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-5]) == "1":
			self.mode = 3 #nacht modus
			self.mode_str = "nachtmodus"
		else:
			self.mode = 4 #anti vries modus
			self.mode_str = "antivriesmodus"
		
		if ((str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-1]) == "1") and ((str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-2]) == "1"):
			self.mode = 0 #disabled
			self.mode_str = "disabled"
		if ((str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-1]) == "1") and ((str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-2]) == "0"):
			self.mode = 5 #manueel
			self.mode_str = "manueel"
		if ((str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-1]) == "0") and ((str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-2]) == "1"):
			self.mode = 6 #timer
			self.mode_str = "timermodus"
		
		#THERMOSTAT OUTPUT BEPALEN UIT DATABYTE4
		message[7] = "222222" + message[7] #string langer gemaakt zodat len() - 8 mogelijk blijft
		
		
		if (str(bin(int(message[7], 16)))[len(str(bin(int(message[7], 16))))-1]) == "1":
			self.zoneaanvraag = True
		else:
			self.zoneaanvraag = False
			
		if (str(bin(int(message[7], 16)))[len(str(bin(int(message[7], 16))))-2]) == "1":
			self.boost = True
		else:
			self.boost = False
			
		if (str(bin(int(message[7], 16)))[len(str(bin(int(message[7], 16))))-3]) == "1":
			self.pompaanvraag = True
		else:
			self.pompaanvraag = False
			
		if (str(bin(int(message[7], 16)))[len(str(bin(int(message[7], 16))))-5]) == "1":
			self.alarm1 = True
		else:
			self.alarm1 = False
			
		if (str(bin(int(message[7], 16)))[len(str(bin(int(message[7], 16))))-6]) == "1":
			self.alarm2 = True
		else:
			self.alarm2 = False
			
		if (str(bin(int(message[7], 16)))[len(str(bin(int(message[7], 16))))-7]) == "1":
			self.alarm3 = True
		else:
			self.alarm3 = False
			
		if (str(bin(int(message[7], 16)))[len(str(bin(int(message[7], 16))))-8]) == "1":
			self.alarm4 = True
		else:
			self.alarm4 = False

		#TEMPERATUUR LEZEN UIT DATABYTE5:
		self.temperatuur = (float(int(message[8],16))/2.0)
		
		#SETPUNT LEZEN UIT DATABYTE6:
		self.sp = (float(int(message[9],16))/2.0)
class VmbPIRM(object):
	'Bewegingsmelder'
	def __init__(self, adres):
		self.adres = adres
		self.message_to_velbus = ""
		self.output_donker = False
		self.output_licht = False
		self.output_bew_1 = False
		self.output_lichtafh_bew_1 = False
		self.output_bew_2 = False
		self.output_lichtafh_bew_2 = False
		self.output_afwezig = False
		
		self.laatste_bew = ""
		self.naam = ""
	def req_status(self):
		mess = []
		mess.append("0f") #start bericht
		mess.append("fb") #low priority
		mess.append(str(self.adres)) #adres van module
		mess.append("02") #aantal byte
		mess.append("fa")
		mess.append ("00") #don't care
		mess = ad_checksum(mess)				
		self.message_to_velbus = ""
		for byte in mess:
			self.message_to_velbus = self.message_to_velbus + byte
			
	def lees_message(self, message):
		#COMMAND_MODULE_STATUS  H'ED
		if message[4] == 'ed':
			#OUTPUTSTATUS BEPALEN UIT DATABYTE2
			message[5] = "222222" + message[5]
			
			if (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-1]) == "1":
				self.output_donker = True
			else:
				self.output_donker = False
				
			if (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-2]) == "1":
				self.output_licht = True
			else:
				self.output_licht = False
				
			if (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-3]) == "1":
				self.output_bew_1 = True
				print "Beweging " + str(self.adres)
			else:
				self.output_bew_1 = False
				
			if (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-4]) == "1":
				self.output_lichtafh_bew_1 = True
			else:
				self.output_lichtafh_bew_1 = False
				
			if (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-5]) == "1":
				self.output_bew_2 = True
			else:
				self.output_bew_2 = False
				
			if (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-6]) == "1":
				self.output_lichtafh_bew_2 = True
			else:
				self.output_lichtafh_bew_2 = False
			
			if (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-7]) == "1":
				self.output_afwezig = True
			else:
				self.output_afwezig = False
		
		#COMMAND_PUSH_BUTTON_STATUS H'00
		if message[4] == '00':
			#OUTPUTSTATUS BEPALEN UIT DATABYTE2 (enkel opkomende meldingen!)
			message[5] = "222222" + message[5]
			
			if (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-1]) == "1":
				self.output_donker = True
				
			if (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-2]) == "1":
				self.output_licht = True
				
			if (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-3]) == "1":
				self.output_bew_1 = True
				self.laatste_bew = datetime.datetime.now()
				
			if (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-4]) == "1":
				self.output_lichtafh_bew_1 = True
				
			if (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-5]) == "1":
				self.output_bew_2 = True
				
			if (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-6]) == "1":
				self.output_lichtafh_bew_2 = True
			
			if (str(bin(int(message[5], 16)))[len(str(bin(int(message[5], 16))))-7]) == "1":
				self.output_afwezig = True
				
			message[6] = "222222" + message[6]
			
			if (str(bin(int(message[6], 16)))[len(str(bin(int(message[6], 16))))-1]) == "1":
				self.output_donker = False
				
			if (str(bin(int(message[6], 16)))[len(str(bin(int(message[6], 16))))-2]) == "1":
				self.output_licht = False
				
			if (str(bin(int(message[6], 16)))[len(str(bin(int(message[6], 16))))-3]) == "1":
				self.output_bew_1 = False
				
			if (str(bin(int(message[6], 16)))[len(str(bin(int(message[6], 16))))-4]) == "1":
				self.output_lichtafh_bew_1 = False
				
			if (str(bin(int(message[6], 16)))[len(str(bin(int(message[6], 16))))-5]) == "1":
				self.output_bew_2 = False
				
			if (str(bin(int(message[6], 16)))[len(str(bin(int(message[6], 16))))-6]) == "1":
				self.output_lichtafh_bew_2 = False
			
			if (str(bin(int(message[6], 16)))[len(str(bin(int(message[6], 16))))-7]) == "1":
				self.output_afwezig = False



			
class Vmb4RYLD(object):
	def __init__(self, adres):
		self.adres = adres
		self.channelstatus = [False, False, False, False, False, False] #CHANNEL 0 bestaat eigenlijk niet...
		self.message_to_velbus = ""
		self.sonoszone = ""
	def toggle_channel(self,channel):	
		if self.channelstatus[channel] == False:
			mess = []
			mess.append("0f") #start bericht
			mess.append("f8") #high priority
			mess.append(str(self.adres)) #adres van module
			mess.append("02") #aantal byte
			mess.append("02") #switch relais on
			mess.append ("0" + str(int_to_bitpos(channel))) #channelnummer
		else:
			mess = []
			mess.append("0f") #start bericht
			mess.append("f8") #high priority
			mess.append(str(self.adres)) #adres van module
			mess.append("02") #aantal byte
			mess.append("01") #switch relais off
			mess.append ("0" + str(int_to_bitpos(channel))) #channelnummer
			
		mess = ad_checksum(mess)
		
		self.message_to_velbus = ""
		
		for byte in mess:
			self.message_to_velbus = self.message_to_velbus + byte
			
	def timer_channel(self,channel,uur, minuten, seconden):	
		mess = []
		mess.append("0f") #start bericht
		mess.append("f8") #high priority
		mess.append(str(self.adres)) #adres van module
		mess.append("05") #aantal byte
		mess.append("03") #start relay timer
		mess.append ("0" + str(int_to_bitpos(channel))) #channelnummer
		mess.append (uur_to_sec(uur,minuten,seconden)[2]) # high byte of delay time
		mess.append (uur_to_sec(uur,minuten,seconden)[1]) # mid byte of delay time
		mess.append (uur_to_sec(uur,minuten,seconden)[0]) # low byte of delay time
			
		mess = ad_checksum(mess)
		
		self.message_to_velbus = ""
		
		for byte in mess:
			self.message_to_velbus = self.message_to_velbus + byte
	
	def req_status(self, channel):
		mess = []
		mess.append("0f") #start bericht
		mess.append("fb") #low priority
		mess.append(str(self.adres)) #adres van module
		mess.append("02") #aantal byte
		mess.append("fa")
		mess.append ("0" + str(int_to_bitpos(channel))) #channel
		mess = ad_checksum(mess)				
		self.message_to_velbus = ""
		
		for byte in mess:
			self.message_to_velbus = self.message_to_velbus + byte
	
	def lees_message(self, message):
		#RELAY_CHANNEL_STATUS H'FB
		if message[4] == 'fb':
			if message[7] == "01":
				self.channelstatus[bitpos_to_int(int(message[5]))] = True
			if message[7] == "00":
				self.channelstatus[bitpos_to_int(int(message[5]))] = False
			if self.sonoszone <> "" and self.channelstatus[5] == True:
				print "channel5 is true"
				#~ for sonoszone in sonoszones:
					#~ if sonoszone.zonenaam == self.sonoszone:
						#~ sonoszone.play()
			if self.sonoszone <> "" and self.channelstatus[5] == False:
				print "channle5 is false"
				#~ for sonoszone in sonoszones:
					#~ if sonoszone.zonenaam == self.sonoszone:
						#~ sonoszone.pause()

class Vmb1BL(object):
	def __init__(self, adres):
		self.adres = adres
		self.status = False #False = laatste actie was omlaag, True = laatste actie was omhoog
		self.actie = 0 #0=off, 1=up, 2=down
		self.message_to_velbus = ""
		
	def toggle(self):
				
		if (self.status == False) and (self.actie == 0): #blind up
			mess = []
			mess.append("0f") #start bericht
			mess.append("f8") #high priority
			mess.append(str(self.adres)) #adres van module
			mess.append("05") #aantal byte
			mess.append("05") #blind up
			mess.append ("03") #channelnummer
			mess.append ("00") #high byte time out
			mess.append ("00") #mid byte time out
			mess.append ("3c") #low byte time out
		elif (self.status == True) and (self.actie == 0): #blind down
			mess = []
			mess.append("0f") #start bericht
			mess.append("f8") #high priority
			mess.append(str(self.adres)) #adres van module
			mess.append("05") #aantal byte
			mess.append("06") #blind down
			mess.append ("03") #channelnummer
			mess.append ("00") #high byte time out
			mess.append ("00") #mid byte time out
			mess.append ("3c") #low byte time out
			
		else: #stop blind	
			mess = []
			mess.append("0f") #start bericht
			mess.append("f8") #high priority
			mess.append(str(self.adres)) #adres van module
			mess.append("02") #aantal byte
			mess.append("04") #switch blind off
			mess.append ("03") #channelnummer

		mess = ad_checksum(mess)
		
		self.message_to_velbus = ""
		
		for byte in mess:
			self.message_to_velbus = self.message_to_velbus + byte
			
	def req_status(self):
		mess = []
		mess.append("0f") #start bericht
		mess.append("fb") #low priority
		mess.append(str(self.adres)) #adres van module
		mess.append("02") #aantal byte
		mess.append("fa")
		mess.append ("03")
		mess = ad_checksum(mess)				
		self.message_to_velbus = ""
		
		for byte in mess:
			self.message_to_velbus = self.message_to_velbus + byte
			
	def lees_message(self, message):
		#COMMAND_BLIND_STATUS H'EC
		if message[4] == 'ec':
			self.actie = int(message[7])
			message[8] = "222222" + message[8]
			if (str(bin(int(message[8], 16)))[len(str(bin(int(message[8], 16))))-8]) == "1":
				self.status = False
			else:
				self.status = True
			if self.actie == 1:
				self.status = True
			if self.actie == 2:
				self.status = False

class Sonoszone(object):
		def __init__(self, zonenaam):
			self.state = ""
			self.zonenaam = zonenaam
			self.zone_list = [] 
		def current_transport_state(self):
			self.zone_list = list(soco.discover())
			if len(self.zone_list) > 0:
				for zone in self.zone_list:
					if zone.player_name == self.zonenaam:
						self.state = zone.get_current_transport_info()['current_transport_state']
						print  zone.player_name + ":  " + self.state
		def play(self):			
			if self.state <> "PLAYING":
				for zone in self.zone_list:
					if zone.player_name == self.zonenaam:
						self.state = zone.get_current_transport_info()['current_transport_state']
						if self.state <> "PLAYING":
							zone.play()
		def pause(self):			
			if self.state == "PLAYING":
				for zone in self.zone_list:
					if zone.player_name == self.zonenaam:
						self.state = zone.get_current_transport_info()['current_transport_state']
						if self.state == "PLAYING":
							zone.pause()
		

def zend_email(to, subject, message):
	# Define email addresses to use
	addr_to   = to
	addr_from = 'pisengard@telenet.be'
 
	# Define SMTP email server details
	smtp_server = 'smtp.telenet.be'

	# Construct email
	
	msg = MIMEText(message)
	msg['To'] = addr_to
	msg['From'] = addr_from
	msg['Subject'] = subject
 
	# Send the message via an SMTP server
	s = smtplib.SMTP(smtp_server)
	s.sendmail(addr_from, addr_to, msg.as_string())
	s.quit()
	print "Successfully sent email with subject: " + subject
	time.sleep(1)
	
def log_message(data):
	
	while len(data) < 14:
		data.append("")
	
	# Open database connection
	db = MySQLdb.connect(host="localhost", user="pi", passwd="pi", db="PiSENDATA")
	# prepare a cursor object using cursor() method
	cursor = db.cursor()
	sql = "INSERT INTO velbuslog(TSTAMP, EVENTDESCR, BYTE0, BYTE1, BYTE2, BYTE3, BYTE4, BYTE5, BYTE6, BYTE7, BYTE8, BYTE9, BYTE10, BYTE11, BYTE12, BYTE13) VALUES ('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')" %(datetime.datetime.today(), '?',data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7], data[8], data[9], data[10], data[11], data[12], data[13])			
	try:
		# Execute the SQL command
		cursor.execute(sql)
		# Commit your changes in the database
		db.commit()
	except:
		# Rollback in case there is any error
		db.rollback()

	# disconnect from server
	db.close()
	time.sleep(0.2)
	
	
def ad_checksum(mess):
	checksum = 0
	for data_byte in mess:
		data_byte = int(data_byte, 16)
		checksum += int(data_byte)
	
	checksum = str(-(checksum % 256) + 256)
	checksum = str(hex(int(checksum)))
	checksum = checksum[2:4]
	while len(checksum) < 2:
		checksum = "0" + checksum
	mess.append(checksum)
	mess.append('04')
	
	return mess
	
def SQLlog_temp(adres, waarde):
	
	# Open database connection
	db = MySQLdb.connect(host="localhost", user="pi", passwd="pi", db="PiSENDATA")
	# prepare a cursor object using cursor() method
	cursor = db.cursor()
	sql = "INSERT INTO temperaturen(TSTAMP, ADRES, WAARDE) VALUES ('%s', '%s', '%s')" %(datetime.datetime.today(), str(adres),waarde)			
	try:
		# Execute the SQL command
		cursor.execute(sql)
		# Commit your changes in the database
		db.commit()
	except:
		# Rollback in case there is any error
		db.rollback()

	# disconnect from server
	db.close()
	time.sleep(0.2)
	
def Plotly_temp(waarde):
	with open('./config.json') as config_file:
		plotly_user_config = json.load(config_file)

		py.sign_in(plotly_user_config["plotly_username"], plotly_user_config["plotly_api_key"])
	
		url = py.plot([
			{
				'x': [], 'y': [], 'type': 'scatter',
				'stream': {
					'token': plotly_user_config['plotly_streaming_tokens'][0],
					'maxpoints': 200
				}
			}], filename='Raspberry Pi Streaming Example Values')

		print "View your streaming graph here: ", url
	
		stream = py.Stream(plotly_user_config['plotly_streaming_tokens'][0])
		stream.open()
	
		# write the data to plotly
		stream.write({'x': datetime.datetime.now(), 'y': waarde})
		print "plotly log"

def bitpos_to_int(channel):
	i = 1 #ingewikkelde manier om van binaire naar bitpositie te gaan...
	x = 1
	while i <> int(channel):
		i = i *2
		x = x+1
	return x
	
def int_to_bitpos(channel):
	channel_int = 1 #channel omzetten van decimaal naar bitpositie
	for a in range((channel -1)):
		channel_int = channel_int*2
	return channel_int
	
def uur_to_sec(uur, minuten, seconden):
	
	seconden = str(hex(seconden + ((int(minuten) + ((int(uur)*60)))*60)))

	byte_low = seconden[(len(seconden)- 2):(len(seconden))]
	if byte_low[0] == "x":
			byte_low = "0" + byte_low[1]
	if len(seconden) >= 5:
		byte_mid = seconden[(len(seconden)- 4):(len(seconden)-2)]
		if byte_mid[0] == "x":
			byte_mid = "0" + byte_mid[1]		
	else:
		byte_mid = "00"
		
	if len(seconden) >= 7:
		byte_high = seconden[(len(seconden)- 6):(len(seconden)-4)]
		if byte_high [0] == "x":
			byte_high  = "0" + byte_high[1]		

	else:
		byte_high = "00"
			
	return (byte_low,byte_mid ,byte_high)

def lees_email():
	while True:
		try:
			pop_conn = poplib.POP3_SSL('pop.telenet.be')
			pop_conn.user('pisengard@telenet.be')
			pop_conn.pass_('hns527')
			
			#Get messages from server:
			messages = [pop_conn.retr(i) for i in range(1, len(pop_conn.list()[1]) + 1)]
			
			# Concat message pieces:
			messages = ["\n".join(mssg[1]) for mssg in messages]
			
			#Parse message intom an email object:
			messages = [parser.Parser().parsestr(mssg) for mssg in messages]
			
			i = 1
			for i, message in enumerate(messages):
			    #~ print message['subject'][0:9]
			    
			    if message['subject'][0:9] == "pisengard":
					print "email voor PiSENGARD  " + str(datetime.datetime.now())
					if message['subject'][10:] == "report":
						
						report = "LAATSTE DETECTIE BEWEGINGSMELDER" + "\n" + "---------------------------------------------" + "\n"
						for pir in pirs:
							report = report + str(pir.naam) + ":  " + str(pir.laatste_bew) + "\n"
						
						
						report = report + "\n" + "TEMPERATUREN" + "\n" + "---------------------" + "\n"
						for thermostat in thermostats:
							report = report + str(thermostat.naam) + ":  " + str(thermostat.temperatuur) + "\n"
							
						report = report + "\n" + "THERMOSTATEN" + "\n" + "---------------------" + "\n"
						for thermostat in thermostats:
							if (thermostat.naam == "keuken") or (thermostat.naam == "badkamer") or (thermostat.naam == "slaapkamer 3"):
								report = report + str(thermostat.naam) + ":  " + str(thermostat.mode_str)
								if thermostat.pompaanvraag:
									report = report + ", pompaanvraag" + "\n"
								else:
									report = report + ", geen pompaanvraag" + "\n"
							
					zend_email('hans_van_gaveren@hotmail.com', 'PiSENGARD report', report)
					pop_conn.dele(i+1)
			pop_conn.quit()
			time.sleep(120)
		except:
				print "email lees error    " + str(datetime.datetime.now())


def main():
	try:
		def lees():
			time.sleep(1)
			print "Starting read_data"
			while True:
				velbusconnectie.read_data()
		
		def schrijf():
			time.sleep(1.5)
			print "Starting write_data"
			while True:
				velbusconnectie.write_data()
			
			
		app = Flask(__name__)
				
		@app.route('/')
		def root():
			return render_template("home.html")
					
		@app.route('/schakel_screen')
		def schakel_screen():
			screen.toggle_blind()
			return redirect('/')
					
		@app.route('/toggle_relais/<adres>/<channel>/<returnadres>')
		def toggle_relais(adres, channel, returnadres):
			for rel in relais:
				if rel.adres == adres:
					rel.toggle_channel(int(channel))
			templatedata = {'thermostat' : thermostat_sk1} #zorgen dat templatedata nooit leeg is
			if returnadres == "sk1":
				templatedata = {'thermostat' : thermostat_sk1}
			elif returnadres == "sk2":
				templatedata = {'thermostat' : thermostat_sk2}
			elif returnadres == "sk3":
				templatedata = {'thermostat' : thermostat_sk3}
			elif returnadres == "gelijkvloers":
				templatedata = {'thermostat' : thermostat_keuken}
			elif returnadres == "badkamer":
				templatedata = {'thermostat' : thermostat_badkamer}
			elif returnadres == "technischeruimte":
				templatedata = {'thermostat' : thermostat_technische_ruimte}
				
			return render_template('%s.html' % returnadres, **templatedata)	
			
		@app.route('/sleeptimer_relais/<adres>/<channel>/<sec>/<returnadres>')
		def sleeptimer_relais(adres, channel, sec, returnadres):
			for rel in relais:
				if rel.adres == adres:
					rel.timer_channel(int(channel),0,0,int(sec))
			return render_template('%s.html' % returnadres)		

		@app.route('/toggle_blind/<adres>/<returnadres>')
		def toggle_blind(adres, returnadres):
			for blind in blinds:
				if blind.adres == adres:
					blind.toggle()
			return render_template('%s.html' % returnadres)
				
		@app.route('/comfort_timer/<adres>/<minuten>/<returnadres>')
		def comfort_timer(adres, minuten, returnadres):
			for thermostat in thermostats:
				if thermostat.adres == adres:
					thermostat.sleeptimer_comfort(int(minuten))
			return render_template('%s.html' % returnadres)
			
#TESTFUNCTIE!!!!!!						
		@app.route('/test')
		def testvelpi():
			#~ zend_email('hans_van_gaveren@hotmail.com', 'PiSENGARD', report)
			return redirect('/')
		@app.route('/reboot')
		def reboot():
			os.system('sudo reboot')
			return redirect('/instellingen')
			
		@app.route('/uitzetten')
		def uitzetten():
			os.system('sudo shutdown -r now')
			return redirect('/instellingen')
			
		@app.route('/golink/<page>')
		def golink(page):
			return render_template('%s.html' % page)
			
		@app.route('/sk1')
		def sk1():
			templatedata = {'thermostat' : thermostat_sk1}
			return render_template("sk1.html", **templatedata)
		@app.route('/sk2')
		def sk2():
			templatedata = {'thermostat' : thermostat_sk2}
			return render_template("sk2.html", **templatedata)
		@app.route('/sk3')
		def sk3():
			templatedata = {'thermostat' : thermostat_sk3}
			return render_template("sk3.html", **templatedata)
		@app.route('/gelijkvloers')
		def gelijkvloers():
			templatedata = {'thermostat' : thermostat_keuken}
			return render_template("gelijkvloers.html", **templatedata)
		@app.route('/badkamer')
		def badkamer():
			templatedata = {'thermostat' : thermostat_badkamer}
			return render_template("badkamer.html", **templatedata)
		@app.route('/technischeruimte')
		def technischeruimte():
			templatedata = {'thermostat' : thermostat_technische_ruimte, 'th_keuken' : thermostat_keuken,'th_badkamer' : thermostat_badkamer,'th_sk3' : thermostat_sk3}
			return render_template("technischeruimte.html", **templatedata)
		@app.route('/instellingen')
		def instellingen():
			templateData = {'printmessage' : velbusconnectie.printmessage, 'logmessage' : velbusconnectie.logmessage, 'maildeurbel' : velbusconnectie.maildeurbel, 'templogging' : velbusconnectie.templogging}		
			return render_template("instellingen.html", **templateData)
		@app.route('/eventlog')
		def eventlog():
			templateData = {'pirs' : pirs}		
			return render_template("eventlog.html", **templateData)
		
		@app.route('/beweging')
		def beweging():
			templateData = {'pirs' : pirs}		
			return render_template("beweging.html", **templateData)

		
		@app.route('/toggle_parameter/<par>')
		def toggle_parameter(par):
			if par == "printmessage":
				velbusconnectie.printmessage = not velbusconnectie.printmessage
				print "printmessage is " + str(velbusconnectie.printmessage)
				
			elif par == "logmessage":
				velbusconnectie.logmessage = not velbusconnectie.logmessage
				print "logmessage is " + str(velbusconnectie.logmessage)
					
			elif par == "maildeurbel":
				velbusconnectie.maildeurbel = not velbusconnectie.maildeurbel
				print "maildeurbel is " + str(velbusconnectie.maildeurbel)
					
			elif par == "templogging":
				velbusconnectie.templogging = not velbusconnectie.templogging
				print "templogging is " + str(velbusconnectie.templogging)
					
			templateData = {'printmessage' : velbusconnectie.printmessage, 'logmessage' : velbusconnectie.logmessage, 'maildeurbel' : velbusconnectie.maildeurbel, 'templogging' : velbusconnectie.templogging}		
			return render_template("instellingen.html", **templateData)
		@app.route('/licht_keuken/<returnadres>')
		def licht_keuken(returnadres):
			relais_g3.toggle_channel(1)
			relais_g1.toggle_channel(1)
			
			templatedata = {'thermostat' : thermostat_sk1} # zorgen dat templatedata nooit leeg is
			if returnadres == "sk1":
				templatedata = {'thermostat' : thermostat_sk1}
			elif returnadres == "sk2":
				templatedata = {'thermostat' : thermostat_sk2}
			elif returnadres == "sk3":
				templatedata = {'thermostat' : thermostat_sk3}
			elif returnadres == "gelijkvloers":
				templatedata = {'thermostat' : thermostat_keuken}
			elif returnadres == "badkamer":
				templatedata = {'thermostat' : thermostat_badkamer}
			elif returnadres == "technischeruimte":
				templatedata = {'thermostat' : thermostat_technische_ruimte}

			
			return render_template('%s.html' % returnadres, **templatedata)
			
			
			
		#maak object velbusconnectie voor communicatie via usb met velbus
		velbusconnectie = Velbusconnection()
		
		#maak relaisobjecten aan, deze worden in een list gezet
		
		relais_g1 = Vmb4RYLD("05")
		relais_g1.sonoszone = "Woonkamer" #Sonos van woonkamer is aan virtuele relais gekoppeld
		relais.append(relais_g1)
		relais_g2 = Vmb4RYLD("03")
		relais.append(relais_g2)
		relais_g3 = Vmb4RYLD("01")
		relais.append(relais_g3)
		relais_k1 = Vmb4RYLD("07")
		relais.append(relais_k1)
		relais_b1 = Vmb4RYLD("08")
		relais.append(relais_b1)
		relais_b2 = Vmb4RYLD("09")
		relais.append(relais_b2)
		relais_CV_RYLD = Vmb4RYLD("32")
		relais.append(relais_CV_RYLD)
		relais_CV_NO = Vmb4RYLD("0D")
		relais.append(relais_CV_NO)
		
		screen = Vmb1BL("21")
		blinds.append(screen)
		blind_sk3 = Vmb1BL("06")
		blinds.append(blind_sk3)
		blind_sk2 = Vmb1BL("0c")
		blinds.append(blind_sk2)
		blind_sk1 = Vmb1BL("0b")
		blinds.append(blind_sk1)
		
		thermostat_keuken = Thermostat("14")
		thermostat_keuken.naam = "keuken"
		thermostats.append(thermostat_keuken)
		thermostat_bureau = Thermostat("19")
		thermostat_bureau.naam = "bureau"
		thermostats.append(thermostat_bureau)
		thermostat_screen = Thermostat("1e")
		thermostat_screen.naam = "screen"
		thermostats.append(thermostat_screen)
		thermostat_sk3 = Thermostat("0e")
		thermostat_sk3.naam = "slaapkamer 3"
		thermostats.append(thermostat_sk3)
		thermostat_wasplaats = Thermostat("24")
		thermostat_wasplaats.naam = "wasplaats"
		thermostats.append(thermostat_wasplaats)
		thermostat_sk2 = Thermostat("2b")
		thermostat_sk2.naam = "slaapkamer 2"
		thermostats.append(thermostat_sk2)
		thermostat_badkamer = Thermostat("2d")
		thermostat_badkamer.naam = "badkamer"
		thermostats.append(thermostat_badkamer)
		thermostat_sk1 = Thermostat("2f")
		thermostat_sk1.naam = "slaapkamer 1"
		thermostats.append(thermostat_sk1)
		thermostat_technische_ruimte = Thermostat("31")
		thermostat_technische_ruimte.naam = "technische ruimte"
		thermostats.append(thermostat_technische_ruimte)
		thermostat_achterdeur = Thermostat("26")
		thermostat_achterdeur.naam = "achterdeur"
		thermostats.append(thermostat_achterdeur)
		thermostat_voordeur = Thermostat("29")
		thermostat_voordeur.naam = "voordeur"
		thermostats.append(thermostat_voordeur)
		
		pir_waskot = VmbPIRM("0A")
		pir_waskot.naam = "waskot"
		pirs.append(pir_waskot)
		pir_keldertrap = VmbPIRM("13")
		pir_keldertrap.naam = "keldertrap"
		pirs.append(pir_keldertrap)
		pir_voordeur = VmbPIRM("27")
		pir_voordeur.naam = "voordeur"
		pirs.append(pir_voordeur)
		pir_WC_G = VmbPIRM("28")
		pir_WC_G.naam = "WC gelijkvloers"
		pirs.append(pir_WC_G)
		pir_WC_B = VmbPIRM("35")
		pir_WC_B.naam = "WC boven"
		pirs.append(pir_WC_B)
		pir_gang = VmbPIRM("36")
		pir_gang.naam = "gang"
		pirs.append(pir_gang)
		
		sonos_woonkamer = Sonoszone("Woonkamer")
		sonoszones.append(sonos_woonkamer)
		sonos_dinoroom = Sonoszone("Dinoroom")
		sonoszones.append(sonos_dinoroom)
				
		thread1 = Thread(target=lees)
		thread1.daemon=True #Bij Ctrl-C ook de thread stoppen
		thread1.start()

		thread2 = Thread(target=schrijf)
		thread2.daemon=True #Bij Ctrl-C ook de thread stoppen
		thread2.start()
		
		thread3 = Thread(target=lees_email)
		thread3.daemon=True #Bij Ctrl-C ook de thread stoppen
		thread3.start()

		
		time.sleep(2)
		print ""
		print "start update relaisblokken"
		for relaisblok in relais:
			print "update relaisblok adres %s" % relaisblok.adres
			relaisblok.req_status(1)
			time.sleep(0.2)
			relaisblok.req_status(2)
			time.sleep(0.2)
			relaisblok.req_status(3)
			time.sleep(0.2)
			relaisblok.req_status(4)
			time.sleep(0.2)
		
		print ""	
		print "start update thermostats"
		for thermostat in thermostats:
			print "update thermostat adres %s" % thermostat.adres
			thermostat.req_status()
			time.sleep(0.5)
			
		print ""	
		print "start update rolluiksturingen"
		for blind in blinds:
			print "update rolluik adres %s" % blind.adres
			blind.req_status()
			time.sleep(0.5)
			
		print ""	
		print "start update bewegingsmelders"
		for pir in pirs:
			print "update bewegingsmelder adres %s" % pir.adres
			pir.req_status()
			time.sleep(0.5)
		print ""
		print "start update sonos"	
		for sonoszone in sonoszones:
			sonoszone.current_transport_state()
		print ""
		print "Starting Flaskserver"
		if __name__ == '__main__':
			#~ app.run(host='0.0.0.0', port=80, debug = True)
			app.run(host='0.0.0.0', port=80)

	except KeyboardInterrupt:
		print "KeyboardInterrupt"
		velbusconnectie.serial.close()

	finally:
		print "finally stop"
		velbusconnectie.serial.close()


if __name__ == '__main__':
	main()
