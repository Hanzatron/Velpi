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
#####################################################################################
#!/usr/bin/python
import serial
import binascii
import time
import datetime
from threading import Thread
from flask import Flask
from flask import request
from flask import render_template
from flask import redirect

message = ""

class Velbusconnection(object):
	def __init__(self):
		self.sleep_after_write = 0.5
		self.message = ""
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
		#~ while True:
			mess = []
			count = 0
			while count < 4:
				data = self.serial.read(1) #1 byte uitlezen
				mess.append (binascii.hexlify(data)) #binaire data omzetten in hexadecimaal
				count = count +1
			count = 0
		
			while count < int(mess[3]):
				data = self.serial.read(1)
				mess.append (binascii.hexlify(data)) #bij in python list zetten
				count = count +1
			count = 0
			while count < 2:
				data = self.serial.read(1)
				mess.append (binascii.hexlify(data))
				count = count +1
		
			messstring = str(datetime.datetime.now()) + " --- "
			for i in mess:
				messstring = messstring + i + " "
			print messstring

	def write_data(self):
		if self.message <> "":
			message = binascii.unhexlify(self.message)
			self.serial.write(message)
			time.sleep(self.sleep_after_write)
			self.message = ""
		
	#~ def run(self):
		#~ print "Logging gestart op " + str(datetime.datetime.now())+"..."
		#~ print ""
		#~ while True:
			#~ read_data()
			#~ write_data()
			
def main():
	try:
		def lees():
			velbusconnectie.read_data()
		
		def schrijf():
			velbusconnectie.write_data()
			time.sleep(0.25)
			
			
		def start_webserver():
			print "Starting Flaskserver"
			app = Flask(__name__)
			
			@app.route('/home')
			def home():
				return render_template("home.html")
			
			@app.route('/')
			def root():
				return render_template("home.html")
			@app.route('/schakel')
			def schakel():
				print "schakel"
				velbusconnectie.message = "0ff8140400020000df04"
				schrijf()
				return redirect('/home')
			
			if __name__ == '__main__':
				app.run(host='0.0.0.0', port=80)
		velbusconnectie = Velbusconnection()

		thread1 = Thread(target=lees)
		thread1.daemon=True #Bij Ctrl-C ook de thread stoppen
		thread2 = Thread(target=start_webserver)
		thread2.daemon=True #Bij Ctrl-C ook de thread stoppen
	
		print "Starting read_data Velbus "
		thread1.start()
		time.sleep(2)
		thread2.start()
		time.sleep(1)
		while 1:
			time.sleep(0.25)
			pass
	except KeyboardInterrupt:
		print "KeyboardInterrupt"
		velbusconnectie.serial.close()

	finally:
		print "finally stop"
		velbusconnectie.serial.close()


if __name__ == '__main__':
  main()
