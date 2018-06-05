import requests
import re
import time
import random
from PIL import Image
import os
from http import cookiejar
import logging
from termcolor import colored
from pymongo import MongoClient
import os
import json
from threading import Thread

import pickle
import json
import traceback

logger = logging.getLogger('wxchat')


class WxChat():
	def __init__(self):
		self.session = requests.session()
		self.headers = {
			'Accept':'application/json, text/plain, */*',
			'User-Agent':'User-Agent: Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 '
						 '(KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36',
			'Content-TType':'application/json; charset=UTF-8'
		}
		# self.session.get('https://wx2.qq.com/?&lang=zh_CN',headers=self.headers)
		self.isLogin = False
		self.conn = MongoClient('mongodb://127.0.0.1:27017')
		self.coll = self.conn.wxchat
		self.db = self.coll.contanctList
		self.cookies=None
		self.memberList = []
		self.members = {}
	def get_time(self):
		return str(int(time.time()*1000))
	def get_r(self):
		s = os.popen('node 1.js').read().replace('\n','')
		return s

	def save_data(self):
		cookies = {}
		for i in self.session.cookies:
			cookies[i.name] = i.value
		data = {
			'cookies': cookies,
			'data': {
				'pass_ticket': self.pass_ticket,
				'wxsid': self.wxsid,
				'wxuin': self.wxuin,
				'skey': self.skey,
				'userInfo': self.userInfo,
				'synckey': self.synckey,
				'DeviceID': self.DeviceID

			},
			'members': self.members,
			'MemberList': self.memberList,
			'USER':self.USER
		}
		# 将数据持续化
		with open('wxchat.pickle', 'wb') as f:
			pickle.dump(data, f)
	def load_data(self):
		logger.warning('加载上次')
		try:
			with open('wxchat.pickle', 'rb') as f:
				data = pickle.load(f)
				self.cookies = data['cookies']
				self.pass_ticket = data['data']['pass_ticket']
				self.wxsid = data['data']['wxsid']
				self.wxuin = data['data']['wxuin']
				self.skey = data['data']['skey']
				self.userInfo = data['data']['userInfo']
				self.synckey = data['data']['synckey']
				self.DeviceID = data['data']['DeviceID']
				self.memberList = data['MemberList']
				self.members = data['members']
				self.USER = data['USER']


			return True
		except Exception as e:
			return False
	def get_utf8(self, str):
		'''
		处理微信编码
		:param str: 要处理的字符
		:return: utf-8编码的字符串
		'''
		return str.encode('ISO-8859-1').decode('utf-8')
	def get_qrcode(self):
		#获取uuid
		url = 'https://login.wx2.qq.com/jslogin?appid={}&redirect_uri=https%3A%2F%2Fwx2.qq.com%2Fcgi-bin%2Fmmwebwx-bin%2Fwebwxnewloginpage&fun=new&lang=zh_CN&_={}'
		url = url.format('wx782c26e4c19acffb',self.get_time())
		res = self.session.get(url,headers=self.headers, verify=False)
		self.uuid = re.findall('uuid = "(.+)";',res.text )[0]
		#通过uuid 获取二维码
		qrcode_url = 'https://login.weixin.qq.com/qrcode/'+self.uuid
		#保存到本地并显示
		with open('qr.png','wb') as f:
			f.write(self.session.get(qrcode_url,headers=self.headers, verify=False).content)
		im = Image.open('qr.png')
		im.show()
		logger.warning('扫码登陆并点击确认登录》》》》')
		# 确认登陆状态 r参数为时间取反



	def check_login(self):
		'''
		循环检查登录状态
		:return:
		'''
		logger.warning('检查登录')
		while True:
			try:
				url = 'https://webpush.wx2.qq.com/cgi-bin/mmwebwx-bin/synccheck?r={}&skey={}&sid={}&uin={}&deviceid={}&synckey={}&_{}'
				syncstr = ''
				for i in self.synckey['List']:
					syncstr += str(i['Key'])
					syncstr += '_'
					syncstr += str(i['Val'])
					syncstr += '|'
				url = url.format(self.get_time(), self.skey, self.wxsid, self.wxuin, self.DeviceID, syncstr[:-1],
								 self.get_time())

				res = self.session.get(url, headers=self.headers, cookies=self.cookies, verify=False, timeout=2)
				print(res.text)
				if 'selector:"2"' in res.text:
					# self.get_new_msg()
					self.get_sync_status()
					# time.sleep(25)
					logger.warning('登录用户为：%s' % self.get_utf8(self.userInfo['NickName']))
					return True
				elif 'retcode:"0",selector:"0"' in res.text:
					return True
				elif 'retcode:"1102' in res.text or '1101' in res.text:
					print('check_res',res.text)
					os.remove('wxchat.pickle')
					self.login()
				else:
					return True

			except Exception as e:
				print(e)

	def get_user_info(self):
		self.get_qrcode()
		check_url = 'https://login.wx2.qq.com/cgi-bin/mmwebwx-bin/login?loginicon=true&uuid={}&tip=0&r={}&_={}'
		check_url = check_url.format(self.uuid, self.get_r(), self.get_time())
		while True:
			try:
				check_res = self.session.get(check_url, headers=self.headers, verify=False).text
				res = re.findall('window.code=200;\s+window.redirect_uri="(.+)";', check_res, re.S)
				if len(res) > 0:
					logger.warning('log success')
					redirect_url = res[0] + '&fun=new&version=v2&lang=zh_CN'
					# 获取用户信息
					self.headers.update({
							'Content-Type': 'application/json; charset=UTF-8'
					})
					get_info = self.session.get(redirect_url, headers=self.headers, verify=False)
					self.isLogin = True
					# 保存session


					self.pass_ticket = re.findall('<pass_ticket>(.+)</pass_ticket>', get_info.text)[0]
					self.wxsid = self.session.cookies.get('wxsid')
					self.wxuin = self.session.cookies.get('wxuin')
					self.skey = re.findall('skey>(.+)</skey>', get_info.text)[0]
					break
			except Exception as e:
				pass
		self.headers.update({'ContentType': 'application/json; charset=UTF-8'})
		url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxinit'
		self.DeviceID = 'e' + str(round(random.random(), 15))[2:17]
		init_url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxinit'

		params = {
				'r':self.get_r(),
				'pass_ticket':self.pass_ticket
		}
		post_data ={
				"BaseRequest":{
					"DeviceID":self.pass_ticket,
					'Sid':self.wxsid,
					'Skey':self.skey,
					'wxuin':self.wxuin,
				}
			}
		headers = {
				'User-Agent': self.headers.get('User-Agent'),
			}
		init_res = self.session.post(init_url,params=params,data=json.dumps(post_data),headers=headers, verify=False, cookies=self.cookies)
		init = init_res.json()
		print(init)
		for i in init['ContactList']:
			if self.get_utf8(i['NickName']) == '陪伴':
				self.USER = i['UserName']
		self.userInfo = init['User']
		self.synckey = init['SyncKey']
		logger.warning('登录用户为：%s' % self.get_utf8(self.userInfo['NickName']))
		self.save_data()
		#获取联系人保存下来
		t = Thread(target=self.get_contact_list)
		logger.warning('单线程刷新联系人列表')
		t.start()



	def get_member(self, username):
		for i in self.memberList:
			if i ['UserName'] == username:
				return i['NickName']
	def start_notify_status(self):
		'''
		开启微信通知  ~
		:return:
		'''
		self.headers['ContentType'] = 'application/json; charset=UTF-8'
		url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxstatusnotify'
		data ={
			"BaseRequest": {
				"Uin": self.wxuin,
				"Sid": self.wxsid,
				"Skey": self.skey,
				"DeviceID": self.DeviceID
			},
			"Code":3,
			"FromUserName": self.userInfo['UserName'],
		    "ToUserName": self.userInfo['UserName'],
		    "ClientMsgId": self.get_time()
		}
		res = self.session.post(url, data=json.dumps(data), headers=self.headers, cookies=self.cookies, verify=False).json()
		if res['BaseResponse']['Ret'] == '0':
			self.MsgId = res['MsgId']

	def get_BaseReq(self):
		return {
				"Uin": self.wxuin,
				"Sid": self.wxsid,
				"Skey": self.skey,
				"DeviceID": self.DeviceID
			}

	def get_sync_status(self):
		print(self.memberList)
		print(self.members)
		logger.warning('waiting for new message......')
		while True:
			url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsync?sid={}&skey={}&lant=zh_CN&pass_picket={}'
			url = url.format(self.wxsid, self.skey, self.pass_ticket)
			rr = os.popen('node 1.js').read()

			data = {"BaseRequest":{
				    "Uin":self.wxuin,
			        "Sid":self.wxsid,
			        "Skey":self.skey,
			        "DeviceID":self.DeviceID
			        },
			        "SyncKey":self.synckey,
			        "rr":rr.strip()
			}
			res = self.session.post(url, data=json.dumps(data), headers=self.headers, verify=False, cookies=self.cookies).json()
			if res['BaseResponse']['Ret'] == 0:
				self.synckey = res['SyncKey']
				if res['AddMsgCount'] >0:
					logger.warning('有%d新消息了: ' % res['AddMsgCount'])

					for i in res['AddMsgList']:
						try:
							if i['FromUserName'] == self.USER:
								a = i['Content'].split('#')
								print(a)
								if len(a)  == 2:

									self.send_msg(a[1],a[0])
							else:

								FromUserName = i['FromUserName']
								logger.warning('{}&{}'.format((i['FromUserName']), self.get_utf8(i['Content'])))
								self.send_msg('%s#%s' % ((i['FromUserName']), self.get_utf8(i['Content'])), self.USER)

						except Exception as e:
							print(e)
							print('消息错误',self.get_utf8(i['Content']))
			time.sleep(1)
	def get_contact_list(self):
		'''
		获取联系人列表
		:return:
		'''
		seq = 0
		colored('正在刷新联系人列表。。。。')
		while True:
			try:
				url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxgetcontact?lang=zh_CN&r={}&seq={}&skey={}'
				url = url.format(self.get_time(), seq, self.skey)
				res = self.session.get(url, headers=self.headers, cookies=self.cookies, verify=False).json()
				seq = res['Seq']
				meberlist = res['MemberList']

				for i in meberlist:
					i['NickName'] = self.get_utf8(i['NickName'])
					i['Province'] = self.get_utf8(i['Province'])
					i['Signature'] = self.get_utf8(i['Signature'])
					i['City'] = self.get_utf8(i['City'])
					self.members[i['UserName']] = i['NickName']
				self.memberList.extend(res['MemberList'])

				if seq == 0:
					print('刷新联系人列表成功:%s' % len(self.memberList))
					self.save_data()
					break
			except Exception as e:
				self.save_data()
				logger.warning('共有%s个联系人' % len(self.memberList))
				self.save_data()
				break
	def send_msg(self, content , ToUserName):
		send_url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendmsg?pass_ticket='+self.pass_ticket
		send_data = {
			"BaseRequest": {
				"Uin": self.wxuin,
				"Sid": self.wxsid,
				"Skey": self.skey,
				"DeviceID": self.DeviceID
			},
			"Msg":
				{
					"Type": 1,
					"Content": content,
					"FromUserName": self.userInfo['UserName'],
					"ToUserName": ToUserName,
					"LocalID": int(time.time() * 10000000),
					"ClientMsgId": int(time.time() * 10000000)
				}, "Scene": 0}
		print(self.headers)
		res = self.session.post(send_url, json=(send_data), headers=self.headers, cookies=self.cookies).json()
		print(res)
		if res['BaseResponse']['Ret'] == 0:
			colored('发送消息成功', 'green')
	def login(self):
		if self.load_data():
			if self.check_login():
				self.isLogin = True
				self.get_sync_status()
		else:
			print(traceback.format_exc())
			self.get_user_info()
			self.get_sync_status()
				# self.
if __name__ == '__main__':
    login = WxChat()
    login.login()
