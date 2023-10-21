import discord
import datetime
import database
import re
import random
import asyncio
from enum import Enum

#Use variables for event states instead of numbers (avoid mistakes)
class Status(Enum):
	UPCOMING = 0
	RUNNING = 1
	FINISHED = 2
	CANCELLED = 3

class Bot(discord.Client):

	def __init__(self):
		super().__init__(intents=discord.Intents.all())
		self.db = database.Database("localhost", "discord_bot_user", "discord_bot_user")
		#Store the last message of an event created by the bot. Only works for one event (cannot have multiple events at a time). If the bot restarts, the message is lost
		#There is no issue if no events are upcoming or running and that the bot restarts
		self.last_event_message_id = None
		#Same as above
		self.event_role_name = None
		#Store the task that runs periodically to check and pdate the status of the upcoming/running event.
		self.current_task = None
		#Boolean that shows if the time remaining before the beginning of an event has already been computed
		self.already_notified = False
		#Store commands that are on cooldown
		self.commands_timeout = list()
		#Duration of all commands timeout in seconds
		self.commands_timeout_duration = 60
		self.sleep_timeout = 0

		self.votes_messages = list()
		self.current_guild = 668925849340215326
		self.log_channel = 1085851613253607504

	async def on_ready(self):
		print('Logged in as')
		print(self.user.name)
		print(self.user.id)
		print('------')

	#Remove all potential risky chars and gets only the LENGTH first chars of the string
	#Return the sanitized message if the message has passed the test and then contains only alphanum (or _-=), else None
	def sanitize(self, message, length):
		message = message[:length]
		harmful = "\"\'\<\>\\\/\^\`\|\(\)\[\]\{\}\~\&\$\£\%\ù\*\#\@\µ\!\§\;\?\,\."
		message = re.sub(r'[' + harmful + ']', '', message)

		if(re.match("^[a-zA-Z0-9\_\-\=]*$", message) != None):
			return message
		else:
			return None


	def random_color(self):
		hexa = "0123456789abcdef"
		random_hex = "0x"
		for i in range(6):
			random_hex += random.choice(hexa)
		return discord.Colour(int(random_hex, 16))

	def create_embed(self, title, description, color, img=""):
		embed = discord.Embed()
		embed.title = title
		embed.description = description
		embed.colour = color
		if(img != ""):
			embed.set_image(url=img)
		return embed

	async def setup_timeout(self, command):
		if command in self.commands_timeout: 
			return False

		self.commands_timeout.append(command)
		return True

	async def run_timeout(self, command, delay):
		
		if(self.sleep_timeout != 0): return

		self.sleep_timeout = self.sleep_timeout + 1
		await asyncio.sleep(delay)
		
		try:
			self.commands_timeout.remove(command)
			self.sleep_timeout = 0
		except:
			pass

	async def print_global_leaderboard(self, description):
		users = self.db.get_all_users_desc()

		if(len(users) == 0): description += "No participants yet"

		count = 1

		for user in users:
			discord_user = await self.fetch_user(user[0])
			if(count == 1):
				place = ':first_place:'
			elif(count == 2):
				place = ':second_place:'
			elif(count == 3):
				place = ':third_place:'
			else:
				place = count

			description += f"{place}. {discord_user.name} - {user[1]} points\n"
			count += 1

		return description

	async def compute_first_bloods(self, event_id, event, description):
		first_bloods = self.db.get_users_first_bloods_by_event_id(event_id)

		if(len(first_bloods) == 0):
			description += "No one flagged in this event"
		else:
			for user in first_bloods:
				discord_user = await self.fetch_user(user[0])

				#Get the time when he submitted the flag and calculate the difference in minutes since the start of the event
				time_diff_obj = user[2] - event[5]
				hours = time_diff_obj.seconds // 3600
				minutes = (time_diff_obj.seconds % 3600) // 60
				seconds = time_diff_obj.seconds % 60

				description += f"**{discord_user.name}** has first blood **{user[1]}** flag in **{hours}h {minutes}m {seconds}s**\n"

		return description

	async def compute_fastest_users(self, event_id, event, description, limit):
		fastest_users = self.db.get_fastest_users_to_complete_event(event_id, limit)

		if(len(fastest_users) == 0):
			description += "No one finished this event"
		else:
			for user in fastest_users:
				discord_user = await self.fetch_user(user[0])

				#Get the time when he submitted the flag and calculate the difference in minutes since the start of the event
				time_diff_obj = user[1] - event[5]
				hours = time_diff_obj.seconds // 3600
				minutes = (time_diff_obj.seconds % 3600) // 60
				seconds = time_diff_obj.seconds % 60

				description += f"**{discord_user.name}** has fully completed the CTF event in **{hours}h {minutes}m {seconds}s**\n"

		return description

	async def event_leaderboard(self, event_id, description, points_per_flag):
		count = 1
		#Get the users who have the correct flags
		users_correct_submissions = self.db.get_users_correct_submissions_by_event_id(event_id)

		for user in users_correct_submissions:
			discord_user = await self.fetch_user(user[0])
			score = int(user[1]) * points_per_flag
			if(count == 1):
				place = ':first_place:'
			elif(count == 2):
				place = ':second_place:'
			elif(count == 3):
				place = ':third_place:'
			else:
				place = count

			description += f"{place}. {discord_user.name} - {score} points\n"
			count += 1

		return description

	#Sends a message by mentionning the role for the current event X minutes before the specified date
	async def notify_before(self, date, channel, minutes_before, embed, role_id):
		#print("enter notify before")
		dt_date = datetime.datetime.strptime(date, '%y-%m-%d - %H:%M:%S')
		dt_now = datetime.datetime.now()
		time_delta = dt_date - dt_now

		#Convert minutes to seconds because we cannot use time_delta.minutes
		minutes_before = minutes_before * 60

		#print(f"Time delta in seconds: {time_delta.seconds} > minutes before: {minutes_before}")

		#Change timezone on the system because UTC instead of UTC+1
		if(time_delta.seconds < minutes_before):
			#print("time_delta < minutes_before")
			await channel.send(role_id)
			await channel.send(embed=embed)
			self.already_notified = True

	async def notify_dm_flag(self, date, channel, minutes_before):
		dt_date = datetime.datetime.strptime(date, '%y-%m-%d - %H:%M:%S')
		dt_now = datetime.datetime.now()
		time_delta = dt_date - dt_now

		#Convert minutes to seconds because we cannot use time_delta.minutes
		minutes_before = minutes_before * 60

		#print(f"Time delta in seconds: {time_delta.seconds} > minutes before: {minutes_before}")

		#Change timezone on the system because UTC instead of UTC+1
		if(time_delta.seconds < minutes_before):
			#print("time_delta < minutes_before")
			await channel.send("A vote for a flag's difficulty is missing!")

	#Convert a date from YYYY-MM-DD HH:MM to datetime format
	async def convert_date_to_datetime(self, date):
		return datetime.datetime.strptime(date + ":00", '%d-%m-%Y %H:%M:%S').strftime("%y-%m-%d - %H:%M:%S")

	#Returns true if dates are correct in the timeframe
	#Used when creating an event
	async def check_dates(self, starting_date, ending_date):
		now = datetime.datetime.now().strftime("%y-%m-%d - %H:%M:%S")
		#If starting date is before now or if event is finished return false
		if(starting_date < now or ending_date < now):
			return False
		#Check if start date is before ending date
		if(ending_date < starting_date):
			return False
		return True

	def reset_variables(self):
		#Cancel the task because the event is over. Reset all the global variables
		self.last_event_message_id = None
		self.event_role_name = None
		self.already_notified = False
		try:
			self.current_task.cancel()
		except:
			pass
		self.votes_messages = list()
		self.commands_timeout = list()
		self.sleep_timeout = 0

	#Reset the global variables and compute things
	def end_event(self, event_id):

		self.reset_variables()

		#Compute the difficulty for the current event
		#This is the only thing we can compute right now, because the points are based on the difficulty and the correct flags have not been added yet.
		votes = self.db.get_all_votes_by_event(event_id)
		number_of_votes = len(votes)
		difficulty = 0

		for vote in votes:
			difficulty = difficulty + vote[3]


		#Exception if no vote
		try:
			total_difficulty = round(difficulty/number_of_votes)
		except:
			total_difficulty = 0

		self.db.update_event_difficulty(event_id, total_difficulty)


		#Compute the correct flags and update points to the users in the case we enter them before the end of the event
		if(len(self.db.get_all_flags_by_event_id(event_id)) != 0):
			flag_points = self.compute_points(event_id)
			flags = self.db.get_all_flags_by_event_id(event_id)

			for flag in flags:
				self.assign_points(event_id, flag[3], flag_points)

	#Function runs every X minutes to check if the current event must be updated (upcoming to running or running to finished)
	#Used to update the states of events
	async def periodic_date_check(self, starting_date, ending_date, event_id, message):
		while True:
			now = datetime.datetime.now().strftime("%y-%m-%d - %H:%M:%S")

			event = self.db.get_event_by_id(event_id)
			#print(f"Event status: {event[0][8]}")
			#If event is finished, update the status of current event to "finished" (2)
			if(ending_date < now):

				#Before updating, check the status. In the case where event is not updated yet
				if(len(self.db.get_event_by_state_and_id(Status.FINISHED.value, event_id)) == 0):
					self.db.update_event_state(event_id, Status.FINISHED.value)

					#Send a message in the event channel tagging the correct role to notify users that the event is over
					log_channel = discord.utils.get(message.guild.channels, id=self.log_channel)
					event_role = discord.utils.get(message.guild.roles, name=self.event_role_name)

					description = "The event " + str(event[0][1]) + " is now over"
					color = self.random_color()
					embed = self.create_embed(str(event[0][1]) + " Event", description, color, "https://www.vulnhub.com/static/img/logo.svg")

					await log_channel.send("<@&" + str(event_role.id) + ">")
					await log_channel.send(embed=embed)

					#Delete the associated role
					await event_role.delete()

					self.end_event(event_id)


			#If starting date is in the past then update the status of current event to "running" (1)
			elif(starting_date < now):
				#print("currently running")
				
				#Before updating, check the status
				if(len(self.db.get_event_by_state_and_id(Status.RUNNING.value, event_id)) == 0):
					#Reset the notification variable
					self.already_notified = False

					self.db.update_event_state(event_id, Status.RUNNING.value)

					#Send a message in the event channel tagging the correct role to notify users that the event is starting
					log_channel = discord.utils.get(message.guild.channels, id=self.log_channel)
					event_role = discord.utils.get(message.guild.roles, name=self.event_role_name)

					description = "The event **" + str(event[0][1]) + "** is starting right now!\n\nGood luck everyone and have fun!"
					color = self.random_color()
					embed = self.create_embed(str(event[0][1]) + " Event", description, color, "https://www.vulnhub.com/static/img/logo.svg")

					await log_channel.send("<@&" + str(event_role.id) + ">")
					await log_channel.send(embed=embed)

				if(not self.already_notified):
					channel = discord.utils.get(message.guild.channels, id=self.log_channel)
					event_role = discord.utils.get(message.guild.roles, name=self.event_role_name)

					description = "The event **" + str(event[0][1]) + "** ends in 15 minutes!"
					color = self.random_color()
					embed = self.create_embed(str(event[0][1]) + " Event", description, color, "https://www.vulnhub.com/static/img/logo.svg")

					await self.notify_before(ending_date, channel, 15, embed, "<@&" + str(event_role.id) + ">")

					#For every flags that have no difficulty given by users. Send a notification to these users.
					for msg in self.votes_messages:
						await self.notify_dm_flag(ending_date, msg.channel, 15)

			#If none of the previous conditions triggered, it means it's still an upcoming event. So do nothing
			else:
				#print("upcoming event")
				#If the event starts in less than 30 minutes then send a message mentionning the event role if it hasn't be done already
				if(not self.already_notified):
					#print("not already notified")
					channel = discord.utils.get(message.guild.channels, id=self.log_channel)
					event_role = discord.utils.get(message.guild.roles, name=self.event_role_name)

					description = "The event **" + str(event[0][1]) + "** starts in **15 minutes**!\n\n:warning: Don't forget to read the <#1085853981831602177> if not already done :warning:\n\nUse ``!help`` in <#1085676265270411344> to get available commands"
					color = self.random_color()
					embed = self.create_embed(str(event[0][1]) + " Event", description, color, "https://www.vulnhub.com/static/img/logo.svg")

					await self.notify_before(starting_date, channel, 15, embed, "<@&" + str(event_role.id) + ">")
				pass

			await asyncio.sleep(5)

	#Create a role for a specific event. Pass the message object to get access to the current guild
	async def create_event_role(self, role_name, message):
		permissions = discord.Permissions(0)
		color = self.random_color()

		self.event_role_name = role_name + " - Notif"

		await message.guild.create_role(name=self.event_role_name, permissions=permissions, colour=color)

	#Once we inserted the flag, calculate the number of points for this flag -> get the global difficulty of the event and perform DEFAULT_POINTS + (DIFFICULTY * 3)
	def compute_points(self, event_id):
		default_points = 10
		difficulty = self.db.get_event_by_id(event_id)[0][7]

		return default_points + (int(difficulty) * 3)


	#Get all submissions for a specific event where the hash is the same, if the hash is the same then get the discord_id and add the score to the corresponding user
	def assign_points(self, event_id, flag, points):
		#Returns a list of users that have the correct flag
		correct_submissions = self.db.get_correct_submissions_by_event_id(event_id, flag)

		for submission in correct_submissions:
			#print("assign " + str(points) + " points to " + str(submission[1]))
			self.db.update_user(submission[1], points)


	async def on_message(self, message):

		if(message.author == self.user):
			return

		#If it's a private message (to the bot)
		if message.channel.type == discord.ChannelType.private:
			if(message.content.startswith("!submit")):
				if(len(message.content.split(" ")) != 2):
					await message.channel.send("Command error!")
					return

				tmp, flag = message.content.split(" ")

				member = await self.fetch_user(message.author.id)

				event = self.db.get_all_events_by_state(Status.RUNNING.value)
				#Check if an event is started
				if(len(event) != 0):
					event_id = event[0][0]
					flag_count = event[0][4]

					#Verify the user exists. If not then insert into users table
					if(len(self.db.get_user_by_id(message.author.id)) == 0):
						#print("User not already in database, create it")
						self.db.insert_into_users(message.author.id, 0)

					#Verify the user hasn't already sent the maximum of submissions for this event
					if(len(self.db.get_user_submissions(message.author.id, event_id)) < int(flag_count)):
						#print("User already in database")
						#print("max flag count for this event not already reached")

						submission_date = datetime.datetime.now()

						flag = self.sanitize(flag, 64)

						if(flag == None):
							await member.send("Sorry message uses forbidden characters, it has not been sent")
							return 

						#Check if user sent this flag already
						user_submissions = self.db.get_user_submissions(message.author.id, event_id)
						for submission in user_submissions:
							if(submission[3] == flag):
								await member.send("You already sent this flag for this event")
								return


						self.db.insert_into_submissions(message.author.id, int(event_id), flag, submission_date)
						#print("Your submission has been transmitted")
						await member.send("Your submission has been transmitted")

						#Let the user vote
						msg = await message.channel.send("Rate the difficulty related to this flag. 0 = very easy, 10 = insane")
						self.votes_messages.append(msg)

						await msg.add_reaction('0️⃣')
						await msg.add_reaction('1️⃣')
						await msg.add_reaction('2️⃣')
						await msg.add_reaction('3️⃣')
						await msg.add_reaction('4️⃣')
						await msg.add_reaction('5️⃣')
						await msg.add_reaction('6️⃣')
						await msg.add_reaction('7️⃣')
						await msg.add_reaction('8️⃣')
						await msg.add_reaction('9️⃣')
						await msg.add_reaction('🔟')
					else:
						await member.send("Sorry you used all your tries :'(")
				else:
					await member.send("Sorry no current event is running :'(")

			#At the end return to avoid the possibility for users to run commands in the bot
			return
		
		if(message.content.startswith("!help")):
			#Timeout, always at the beginning
			cmd = message.content.split(" ")[0]
			if(await self.setup_timeout(cmd)):

				description = ":fire: **Admin commands** :fire:\n\n"

				description += "**`!start_event`**: Starts a new upcoming event. The starting date must be in the future. The number of flags cannot be modified afterwards.\n"
				description += "**Syntax**: *!start_event EVENT_NAME | EVENT_DESCRIPTION | EVENT_URL | NUMBER_OF_FLAGS | STARTING_DATE | ENDING_DATE*\n"
				description += "**Example**: ``!start_event | My new CTF3 | This is a description | https://blog.synoslabs.com | 2 | 15-03-2023 08:00 | 15-03-2023 23:59``\n\n"
				
				description += "**`!stop_event`**: Stops a currently running event. Calculate flags points if already given by an admin\n"
				description += "**Syntax**: *!stop_event*\n"
				description += "**Example**: ``!stop_event``\n\n"

				description += "**`!cancel_event`**: Cancels an upcoming or running event. If users have already submitted some flags, ignore them.\n"
				description += "**Syntax**: *!cancel_event*\n"
				description += "**Example**: ``!cancel_event``\n\n"

				description += "**`!add_flag`**: Adds a new correct flag hash for a running or finished event.\n"
				description += "**Syntax**: *!add_flag EVENT_ID FLAG_NAME HASH*\n"
				description += "**Example**: ``!add_flag 110 user e103d5d50e8f5c69b0f8d7e5bad4ebf1``\n\n"

				description += "**`!update_flag`**: Modifies a flag hash for a running or finished event.\n"
				description += "**Syntax**: *!update_flag EVENT_ID FLAG_NAME NEW_HASH*\n"
				description += "**Example**: ``!update_flag 110 user cc414bfc9c00475b59c87595299ff31d``\n\n\n"


				description += ":gear: **User commands** :gear:\n\n"

				description += "**`!submit`**: :warning: **MUST BE SENT DIRECTLY TO THE BOT!** :warning: Submits a specific hash for the running event. Once a flag is submitted, it cannot be modified or deleted.\n"
				description += "**Syntax**: *!submit HASH*\n"
				description += "**Example**: ``!submit 0800fc577294c34e0b28ad2839435945``\n\n"

				description += "**`!upcoming`**: Lists basic information about the upcoming event\n"
				description += "**Syntax**: *!upcoming*\n"
				description += "**Example**: ``!upcoming``\n\n"

				description += "**`!running`**: Lists basic information about the running event\n"
				description += "**Syntax**: *!running*\n"
				description += "**Example**: ``!running``\n\n"

				description += "**`!finished`**: Lists basic information about all the finished events\n"
				description += "**Syntax**: *!finished*\n"
				description += "**Example**: ``!finished``\n\n"

				description += "**`!leaderboard`**: Shows the global leaderboards containing users and their points\n"
				description += "**Syntax**: *!leaderboard*\n"
				description += "**Example**: ``!leaderboard``\n\n"

				description += "**`!info`**: Shows a detailed view about a specific event (upcoming, running or finished)\n"
				description += "**Syntax**: *!info EVENT_ID*\n"
				description += "**Example**: ``!info 118``\n\n"


				color = self.random_color()
				embed = self.create_embed(f"Help Menu", description, color, "https://www.vulnhub.com/static/img/logo.svg")

				await message.channel.send(embed=embed)


			#Run timeout for X seconds
			#Always at the end
			await self.run_timeout(cmd, self.commands_timeout_duration)

		#Start a new event only if the command is sent by me.
		if(message.content.startswith("!start_event") and message.author.id == 385035509736407040):
			#Check if parameters are missing
			if(len(message.content.split("|")) != 7):
				await message.channel.send("Command error!")
				return

			cmd, name, description, url, number_of_flags, starting_date, ending_date = [s.strip() for s in message.content.split("|")]

			#Date conversion to DATETIME type for mysql
			try:
				starting_date_datetime = await self.convert_date_to_datetime(starting_date)
				ending_date_datetime = await self.convert_date_to_datetime(ending_date)
			except ValueError:
				await message.channel.send("Problem with dates, verify the timeframe")
				return

			#Check dates
			if(not await self.check_dates(starting_date_datetime, ending_date_datetime)):
				await message.channel.send("Problem with dates, verify the timeframe")
				return

			#When we create an event, check every X minutes if the event has started or has ended (create task of check_dates()). 
			#If the event has started then update the status in the database.
			#If the event ended, update the status, remove the roles, set self variables to None, stop the task
			#https://stackoverflow.com/questions/61920560/how-to-loop-a-task-in-discord-py

			event_id = self.db.insert_into_events(name, description, url, number_of_flags, starting_date_datetime, ending_date_datetime)
			await self.create_event_role(name, message)

			await message.channel.send("Event and role created!")



			description = f"**A new event is planned!**\n\n**Starting date:** {starting_date}\n**Ending date:** {ending_date}\n\n**Event description:**\n{description}\n\n**URL:** {url}\n\nYou can react to this message with the ✅ reaction to get notified about this event.\n\nYou'll be notified **15 minutes before** the beginning of the event.\n\n:warning: **Don't forget to read the** <#1085853981831602177> :warning:"

			#Setup the sending of announcement message in appropriate channel
			color = self.random_color()
			embed = self.create_embed(name + " Event", description, color, "https://www.vulnhub.com/static/img/logo.svg")

			#Change the channel name to match the announcement channel
			log_channel = discord.utils.get(message.guild.channels, id=self.log_channel)

			#Mention everyone (not in embed because ping doesn't work in it)
			#await log_channel.send("@everyone")
			event_message = await log_channel.send(embed=embed)

			self.last_event_message_id = event_message.id
			await event_message.add_reaction("✅")

			#Must be the last line of the !start_event command
			#Message is passed as argument to get guild ID from it.
			self.current_task = self.loop.create_task(self.periodic_date_check(starting_date_datetime, ending_date_datetime, event_id, message))

		#Stop the current event
		if(message.content.startswith("!stop_event") and message.author.id == 385035509736407040):
			if(len(message.content.split(" ")) != 1):
				await message.channel.send("Command error!")
				return

			#If an event is currently running, update it's status to FINISHED
			if(len(self.db.get_all_events_by_state(Status.RUNNING.value)) != 0):
				event = self.db.get_all_events_by_state(Status.RUNNING.value)[0]
				event_id = event[0]
				event_name = event[1]

				self.db.update_event_state(event_id, Status.FINISHED.value)

				await message.channel.send(f"Event {event_name} (ID: {event_id}) successfully stopped! Do not forget to use !add_flag if not already done")

				self.end_event(event_id)

				event_role = discord.utils.get(message.guild.roles, name=self.event_role_name)

				description = f"The event {str(event_name)} (ID: {event_id}) is now over"
				color = self.random_color()
				embed = self.create_embed(str(event_name) + " Event", description, color, "")


				log_channel = discord.utils.get(message.guild.channels, id=self.log_channel)

				await log_channel.send("<@&" + str(event_role.id) + ">")
				await log_channel.send(embed=embed)

				#Delete the associated role
				await event_role.delete()

			else:
				await message.channel.send("There is no current event running")

		#Cancel an upcoming or running event
		if(message.content.startswith("!cancel_event") and message.author.id == 385035509736407040):
			#Check if parameters are missing
			if(len(message.content.split(" ")) != 1):
				await message.channel.send("Command error!")
				return

			#If the event exists and is upcoming then change its state to cancelled (3)
			if(len(self.db.get_all_events_by_state(Status.UPCOMING.value)) != 0):
				event = self.db.get_all_events_by_state(Status.UPCOMING.value)[0]
				event_id = event[0]
				event_name = event[1]
				self.db.update_event_state(event_id, Status.CANCELLED.value)
				#Delete the associated role
				event_role = discord.utils.get(message.guild.roles, name=self.event_role_name)


				description = f"The upcoming event (ID: {event_id}) is cancelled"
				color = self.random_color()
				embed = self.create_embed(str(event_name) + " Event", description, color, "")

				log_channel = discord.utils.get(message.guild.channels, id=self.log_channel)

				await log_channel.send("<@&" + str(event_role.id) + ">")
				await log_channel.send(embed=embed)

				await event_role.delete()

				#Cancel the task because the event is over
				self.reset_variables()

				await message.channel.send("Event successfully cancelled!")

				#Stop the loop that checks if current state's event must be changed
				self.current_task.cancel()
				return
			elif(len(self.db.get_all_events_by_state(Status.RUNNING.value)) != 0):
				event_id = self.db.get_all_events_by_state(Status.RUNNING.value)[0][0]
				self.db.update_event_state(event_id, Status.CANCELLED.value)

				#Delete the associated role
				event_role = discord.utils.get(message.guild.roles, name=self.event_role_name)

				description = f"The running event (ID: {event_id}) is cancelled"
				color = self.random_color()
				embed = self.create_embed(str(event_name) + " Event", description, color, "")

				log_channel = discord.utils.get(message.guild.channels, id=self.log_channel)

				await log_channel.send("<@&" + str(event_role.id) + ">")
				await log_channel.send(embed=embed)

				await event_role.delete()

				#Cancel the task because the event is over
				self.reset_variables()


				self.db.update_event_state(event_id, Status.CANCELLED.value)
				self.db.delete_submissions_by_event_id(event_id)
				self.db.delete_votes_by_event_id(event_id)

				await message.channel.send("Event successfully cancelled!")

			else:
				await message.channel.send("Can't cancel this event. Is it existing or upcoming?")
				return

		#Add the correct flags for a specific event. Will be used to calculate points for users
		if(message.content.startswith("!add_flag") and message.author.id == 385035509736407040):

			if(len(message.content.split(" ")) != 4):
				await message.channel.send("Command error!")
				return

			cmd, event_id, flag_name, flag = message.content.split(" ")
			
			#Check if event exists
			if(len(self.db.get_event_by_id(event_id)) == 0): 
				await message.channel.send("Event doesn't exist")
				return

			#Check if the number of flags for this event hasn't been reached yet
			if(len(self.db.get_all_flags_by_event_id(event_id)) >= self.db.get_event_by_id(event_id)[0][4]): 
				await message.channel.send("All the flags are already given for this event")
				return

			#Only insert the flag. But compute at the end of the event
			if(self.db.insert_into_flags(flag_name, event_id, flag) != None):
				await message.channel.send(f"Flag {flag} successfully inserted!")

			#If the event is still running then wait the end of it before calculating the points
			if(len(self.db.get_event_by_state_and_id(Status.RUNNING.value, event_id)) == 0):
				flag_points = self.compute_points(event_id)
				self.assign_points(event_id, flag, flag_points)


		if(message.content.startswith("!update_flag") and message.author.id == 385035509736407040):

			if(len(message.content.split(" ")) != 4):
				await message.channel.send("Command error!")
				return

			cmd, event_id, flag_name, new_flag = message.content.split(" ")

			#Check if event exists
			if(len(self.db.get_event_by_id(event_id)) == 0): 
				await message.channel.send("Event doesn't exist")
				return

			#Check if flag name for an event exists
			if(len(self.db.get_flag_by_event_and_name(event_id, flag_name)) == 0): 
				await message.channel.send(f"Flag {flag_name} doesn't exist for this event")
				return

			old_flag = self.db.get_flag_by_event_and_name(event_id, flag_name)

			flag_points = self.compute_points(event_id)

			#Remove points from users who had the correct old flag
			self.assign_points(event_id, old_flag[0][3], - flag_points)
			#Update the new flag in database
			self.db.update_flag_hash(flag_name, event_id, new_flag)
			#Assign points to users who have the correct new flag
			self.assign_points(event_id, new_flag, flag_points)

			await message.channel.send(f"Flag {flag_name} has been changed to {new_flag} and points for users have been modified!")


		if(message.content.startswith("!upcoming") and message.channel.id == 1085676265270411344):
			#Timeout, always at the beginning
			cmd = message.content.split(" ")[0]
			if(await self.setup_timeout(cmd)):

				if(len(self.db.get_all_events_by_state(Status.UPCOMING.value)) != 0):
					#Get the upcoming event
					upcoming_event = self.db.get_all_events_by_state(Status.UPCOMING.value)[0]

					description = f"\nStarting date: {upcoming_event[5]}\nEnding date: {upcoming_event[6]}\n"
					color = self.random_color()
					embed = self.create_embed(f"{upcoming_event[1]} Event (ID: {upcoming_event[0]})", description, color, "https://www.vulnhub.com/static/img/logo.svg")

					await message.channel.send(embed=embed)
				else:
					await message.channel.send("No upcoming event planned")

			#Run timeout for 60 seconds
			#Always at the end
			await self.run_timeout(cmd, self.commands_timeout_duration)


		if(message.content.startswith("!running") and message.channel.id == 1085676265270411344):
			#Timeout, always at the beginning
			cmd = message.content.split(" ")[0]
			if(await self.setup_timeout(cmd)):

				if(len(self.db.get_all_events_by_state(Status.RUNNING.value)) != 0):
					#Get the upcoming event
					running_event = self.db.get_all_events_by_state(Status.RUNNING.value)[0]
					number_participants = self.db.get_event_number_participants(running_event[0])[0][0]
					number_submissions = self.db.get_number_submissions_by_event_id(running_event[0])[0][0]

					description = f"\nStarting date: {running_event[5]}\nEnding date: {running_event[6]}\n\nCurrent number of participants: {number_participants}\nCurrent number of flags submitted: {number_submissions}"
					color = self.random_color()
					embed = self.create_embed(f"{running_event[1]} Event (ID: {running_event[0]})", description, color, "https://www.vulnhub.com/static/img/logo.svg")

					#select count(DISTINCT discord_id) from submissions where event_id = X

					await message.channel.send(embed=embed)
				else:
					await message.channel.send("No event is currently running")

			#Run timeout for 60 seconds
			#Always at the end
			await self.run_timeout(cmd, self.commands_timeout_duration)


		if(message.content.startswith("!finished") and message.channel.id == 1085676265270411344):
			#Timeout, always at the beginning
			cmd = message.content.split(" ")[0]
			if(await self.setup_timeout(cmd)):

				if(len(self.db.get_all_events_by_state(Status.FINISHED.value)) != 0):
					#Get the upcoming event
					finished_events = self.db.get_all_events_by_state(Status.FINISHED.value)

					description = ""

					for finished_event in finished_events:
						number_participants = self.db.get_event_number_participants(finished_event[0])[0][0]
						description += f"------------------------------------\n{finished_event[1]} (ID: {finished_event[0]})\nStarting date: {finished_event[5]}\nEnding date: {finished_event[6]}\nNumber of participants: {number_participants}\n------------------------------------\n\n"

					color = self.random_color()
					embed = self.create_embed("List of ended events", description, color, "https://www.vulnhub.com/static/img/logo.svg")

					await message.channel.send(embed=embed)
				else:
					await message.channel.send("No finished event to list")

			#Run timeout for 60 seconds
			#Always at the end
			await self.run_timeout(cmd, self.commands_timeout_duration)


		if(message.content.startswith("!leaderboard") and message.channel.id == 1085676265270411344):
			#Timeout, always at the beginning
			cmd = message.content.split(" ")[0]
			if(await self.setup_timeout(cmd)):
				description = ""
				description = await self.print_global_leaderboard(description)
				
				color = self.random_color()
				embed = self.create_embed("Leaderboard", description, color, "https://www.vulnhub.com/static/img/logo.svg")

				await message.channel.send(embed=embed)

			#Run timeout for 60 seconds
			#Always at the end
			await self.run_timeout(cmd, self.commands_timeout_duration)


		if(message.content.startswith("!info") and message.channel.id == 1085676265270411344):
			#Timeout, always at the beginning
			cmd = message.content.split(" ")[0]
			if(await self.setup_timeout(cmd)):

				if(len(message.content.split(" ")) != 2):
					await message.channel.send("Command error!")
					return

				data = message.content.split(" ")[1]

				#--------------------------------------------------------------------------------------------------------------------------------
				#Part for a user -> !info @USER

				if(data.startswith("<@")):
					user_id_regex = re.compile("<@!?(?P<id>[0-9]+)>")
					match = user_id_regex.search(data)
					if match:
						user_id = match.group("id")
						try:
							user = await self.fetch_user(user_id)
						except:
							await message.channel.send("User doesn't exist...")
							return

						#Number of points
						total_points = self.db.get_points_user(user_id)

						#Leaderboard rank
						try:
							rank = self.db.get_user_rank_leaderboard(user_id)[0][0]

							if(rank == 1):
								place = ':first_place:'
							elif(rank == 2):
								place = ':second_place:'
							elif(rank == 3):
								place = ':third_place:'
							else:
								place = rank
						except:
							place = "Unranked"

						#Number of participations
						try:
							number_of_participations = self.db.get_user_number_participations(user_id)[0][0]
						except:
							number_of_participations = 0

						#Number of submitted flags
						try:
							number_of_submitted_flags = self.db.get_user_number_flags_submitted(user_id)[0][0]
						except:
							number_of_submitted_flags = 0

						#Number of correct flags
						try:
							number_of_correct_flags = self.db.get_user_number_correct_flags(user_id)[0][0]
						except:
							number_of_correct_flags = 0

						#Number of first bloods
						try:
							number_of_first_bloods = self.db.get_user_number_first_bloods(user_id)[0][0]
						except:
							number_of_first_bloods = 0


						#List of event he participated
						event_list = self.db.get_all_events_where_user_participated(user_id)

						if(len(event_list) != 0):
							ids = [event[0] for event in event_list]
							ids_string = ', '.join(str(id) for id in ids)
						else:
							ids_string = "**No event yet**"


						description = f"ID: **{user.id}**\nUsername: **{user.name}**\n\nTotal points: **{total_points} points**\nGlobal rank: **{place}**\n\nNumber of participations: **{number_of_participations}**\nNumber of submitted flags: **{number_of_submitted_flags}**\nNumber of correct flags: **{number_of_correct_flags}**\nNumber of first bloods: **{number_of_first_bloods}**\n\nList of events user participated to: {ids_string}"
						
						color = self.random_color()
						embed = self.create_embed(f"User Stats", description, color, "https://www.vulnhub.com/static/img/logo.svg")

						await message.channel.send(embed=embed)


					else:
						await message.channel.send("Error formating")

				else:
					#--------------------------------------------------------------------------------------------------------------------------------
					#Part for an event -> !info <EVENT_ID>
					
					event_id = self.sanitize(message.content.split(" ")[1], 8)

					if(event_id == None):
						await message.channel.send("Format of event isn't correct")
						return

					#Check if event exists
					if(len(self.db.get_event_by_id(event_id)) == 0): 
						await message.channel.send("Event doesn't exist")
						return

					#Check the status and add different description depending on the status
					event = self.db.get_event_by_id(event_id)[0]
					
					#These fields are the same whatever the event's status 
					description = f"**Description:** {event[2]}\n\n**URL:** {event[3]}\n\nStarting date: **{event[5]}**\nEnding date: **{event[6]}**\n\n:triangular_flag_on_post: Number of flags: **{event[4]}**"


					if(event[8] == Status.UPCOMING.value):
						#Add the status at the beginning
						description = "Status: **upcoming**\n\n" + description
					elif(event[8] == Status.RUNNING.value):
						#Add the status at the beginning
						description = "Status: **running**\n\n" + description
						number_participants = self.db.get_event_number_participants(event_id)[0][0]
						number_submissions = self.db.get_number_submissions_by_event_id(event_id)[0][0]
						description += f"\n\nCurrent number of participants: **{number_participants}**\nCurrent number of flags submitted: **{number_submissions}**"
						#Here we cannot compute the current leaderboard for this event because we don't know yet the difficulty and number of points per flag.


					elif(event[8] == Status.FINISHED.value):
						#Add the status at the beginning
						description = "Status: **finished**\n\n" + description
						number_participants = self.db.get_event_number_participants(event_id)[0][0]
						number_submissions = self.db.get_number_submissions_by_event_id(event_id)[0][0]
						number_correct_flags = self.db.count_correct_submissions_by_event_id(event_id)[0][0]
						#Get the number of points earned by flag, depending on the difficulty
						points_per_flag = self.compute_points(event_id)
						description += f"\n\nDifficulty: **{event[7]}/10**\nNumber of participants: **{number_participants}**\nNumber of flags submitted: **{number_submissions}**\nNumber of correct flags: **{number_correct_flags}**\nValue of a flag: **{points_per_flag} points**\n"
						
						#First bloods
						description += "\n\n:drop_of_blood: **First bloods** :drop_of_blood:\n\n"
						description = await self.compute_first_bloods(event_id, event, description)

						#Top X fastest users to submit all correct flags
						description += "\n\n:clap: **Fastest users to complete CTF** :clap:\n\n"
						description = await self.compute_fastest_users(event_id, event, description, 3)
						
						#Leaderboard for the event
						description += "\n\n:trophy: **Event leaderboard** :trophy:\n\n"
						description = await self.event_leaderboard(event_id, description, points_per_flag)

					color = self.random_color()
					embed = self.create_embed(f"{event[1]} Event (ID: {event[0]})", description, color, "https://www.vulnhub.com/static/img/logo.svg")

					await message.channel.send(embed=embed)

			#Run timeout for 60 seconds
			#Always at the end
			await self.run_timeout(cmd, self.commands_timeout_duration)

		#This command is only used once, to write down the rules to the #rules-event channel. Then it is not needed anymore
		# if(message.content.startswith("!rules")):
		# 	#Timeout, always at the beginning
		# 	cmd = message.content.split(" ")[0]
		# 	if(await self.setup_timeout(cmd)):

		# 		color = self.random_color()

		# 		description = ":gear: **Liste des salons** :gear:\n\n"
		# 		description += "<#1085853981831602177> : contient les **règles** concernant les events.\n"
		# 		description += "<#1085851613253607504> : correspond aux **annonces** des events quand ceux-ci sont **plannifiés**, sur le point d'être **lancés** ou **arrêtés**.\n"
		# 		description += "<#1085676265270411344> : permet de lancer les commandes de bot. Les commandes ne fonctionnent **que dans ce salon**.\n"
		# 		description += "<#1085676193694630038> et <#1085676526189682781> : salons dédiés pour les **questions** et pour **communiquer** lors des events.\n\n\n"

		# 		description += ":question: **C'est quoi ?** :question:\n\n"
		# 		description += "Ce sont des évènements organisés régulièrement par <@!385035509736407040> en direct sur Twitch (http://twitch.tv/kr0wz_) dont le but est d'apprendre et s'entraîner en faisant des CTFs (ou boot2root).\n\n"
		# 		description += "Pour réussir un CTF il faut collecter des \"flags\". Il s'agit de chaînes de caractères (souvent des hashs) qui permettent de prouver qu'on a bien réussi à exploiter une machine. On les trouve principalement dans les répertoires user (user.txt) et root (root.txt). Mais il se peut parfois que les flags ne suivent pas cette convention.\n\n\n"

		# 		description += ":question: **Comment je sais quand un nouveau event va avoir lieu ?** :question:\n\n"
		# 		description += "Tous les évènements sont **planifiés à l'avance**. Vous pouvez cliquer sous le message d'annonce du bot (<#1085851613253607504>) pour être **notifié** du début et des autres annoncés liées à cet évènement.\n\n"
		# 		description += "Sachant qu'il y peut y avoir des petites connexions. J'essaie de plannifier un évènement plusieurs heures (voir jours) en avance pour laisser le temps aux personnes voulant participer de télécharger la machine (si on fait du Vulnhub par exemple).\n\n\n"

		# 		description += ":question: **Comment participer ?** :question:\n\n"
		# 		description += "N'importe qui peut participer (débutant, expert, curieux, etc...), il suffit d'attendre qu'un event soit en cours. Et de soumettre les bons flags directement en message privé à <@!1003035084795936808> avec la commande ``!submit HASH`` (exemple : ``!submit cc414bfc9c00475b59c87595299ff31d``).\n\n"
		# 		description += "Attention à bien regarder le nombre de flags qu'il faut rentrer pour l'évènement.\n\n"
		# 		description += "Dans le cas où le flag n'est pas un hash mais une autre chaîne de caractères (phrase, ASCII art, etc...), il faut alors entrer le **checksum MD5 du fichier** en tant que flag. Sous Linux, cela se fait avec la commande ``md5sum user.txt``\n\n"
		# 		description += "En cas de doute sur une commande : ``!help`` dans <#1085676265270411344> ou bien vous pouvez me ping directement <@!385035509736407040>\n\n"
		# 		description += ":warning: Il n'est **pas possible** de modifier ou supprimer un flag une fois qu'il a été soumis au bot. :warning:\n\n\n"

		# 		description += ":question: **Qu'est-ce qu'il y a à gagner ?** :question:\n\n"
		# 		description += "**Rien du tout !** (si ce n'est la fierté d'avoir progressé)\n\n"
		# 		description += "Le but est de partager ses connaissances et progresser ensemble en faisant des CTFs.\n\n\n"

		# 		description += ":question: **Comment sont calculés les points ?** :question:\n\n"
		# 		description += "Par défaut chaque flag rapport **10 points**.\n\n"
		# 		description += "Le niveau de difficulté est calculé en **fonction des notes** que chaque utilisateur donne aux flags lorsqu'ils les soumettent en message privé au bot.\n\n"
		# 		description += "De ce fait, 1 point de difficulté supplémentaire ajoute 3 points à chaque flag. On peut donc avoir au minimum un flag qui vaut **10 points** (si difficulté = 0/10) et au maximum **40 points** (si difficulté = 10/10).\n\n"
		# 		description += "La fonction de calcul est la suivante : ``NOMBRE POINTS = 10 + (DIFFICULTE * 3)``\n\n"
		# 		description += "Dans un event, tous les flags rapportent le **même nombre de points** (user, root, etc...). Il n'y a que la **difficulté globale** du CTF qui influe sur les points.\n\n\n"


				
		# 		embed = self.create_embed(f"Infos", description, color, "https://www.vulnhub.com/static/img/logo.svg")
		# 		rules_channel = discord.utils.get(message.guild.channels, id=1085853981831602177)
		# 		await rules_channel.send(embed=embed)

		# 		#Must split, else message is too long

		# 		description = ":checkered_flag: **Règles** :checkered_flag:\n\n"
		# 		description += "Le but premier est **d'apprendre** et **s'entraîder**. Il est donc fortement conseillé de **ne pas tricher**.\n"
		# 		description += "Un exemple de triche serait de faire le CTF en avance (a partir du moment où il est annoncé).\n"
		# 		description += "Il ne nous est pas possible de vérifier si quelqu'un a triché mais cela n'a **aucun intérêt**.\n"
		# 		description += "Vous pouvez faire le **CTF à plusieurs** si vous le souhaitez, l'entraîde est toujours la bienvenue.\n"
		# 		description += "Vous pouvez aussi **m'aider en direct** sur mon live Twitch (https://twitch.tv/kr0wz_). Cependant essayez de ne **pas spoil** les étapes et ce qu'il faut faire pour résoudre le CTF.\n\n\n"

		# 		description += ":warning: Le non respect des règles peut entraîner un **avertissement** ou une **sanction** plus importante en cas de récidive. :warning:\n\n\n"

		# 		description += ":triangular_flag_on_post: **Merci et bon CTF à vous !** :triangular_flag_on_post:"

		# 		embed = self.create_embed(f"Infos", description, color, "https://www.vulnhub.com/static/img/logo.svg")
		# 		await rules_channel.send(embed=embed)


		# 	#Run timeout for X seconds
		# 	#Always at the end
		# 	await self.run_timeout(cmd, self.commands_timeout_duration)
			

	#Triggered when a reaction is added to a message
	async def on_raw_reaction_add(self, payload):
		#Do not trigger this function if the bot adds an emoji itself
		if(payload.member == self.user):
			return

		if(payload.user_id == self.user.id):
			return

		for msg in self.votes_messages:
			if(payload.message_id == msg.id):
				#print("user has vote already")
				if(payload.emoji.name == "0️⃣" or payload.emoji.name == "1️⃣" or payload.emoji.name == "2️⃣" or payload.emoji.name == "3️⃣" or payload.emoji.name == "4️⃣" or payload.emoji.name == "5️⃣" or payload.emoji.name == "6️⃣" or payload.emoji.name == "7️⃣" or payload.emoji.name == "8️⃣" or payload.emoji.name == "9️⃣" or payload.emoji.name == "🔟"):
					guild = self.get_guild(self.current_guild)
					member = discord.utils.get(guild.members, id=payload.user_id)

					event_id = self.db.get_all_events_by_state(Status.RUNNING.value)[0][0]
					note = None

					#Convert emoji to corresponding int
					if(payload.emoji.name == "0️⃣"): note = 0 
					elif(payload.emoji.name == "1️⃣"): note = 1
					elif(payload.emoji.name == "2️⃣"): note = 2
					elif(payload.emoji.name == "3️⃣"): note = 3
					elif(payload.emoji.name == "4️⃣"): note = 4
					elif(payload.emoji.name == "5️⃣"): note = 5
					elif(payload.emoji.name == "6️⃣"): note = 6
					elif(payload.emoji.name == "7️⃣"): note = 7
					elif(payload.emoji.name == "8️⃣"): note = 8
					elif(payload.emoji.name == "9️⃣"): note = 9
					elif(payload.emoji.name == "🔟"): note = 10

					#Insert into database
					self.db.insert_into_votes(payload.user_id, event_id, note)

					#Remove message from list
					self.votes_messages.remove(msg)

		#Check if a user adds an emoji to the event message to get the notification role
		if(payload.message_id == self.last_event_message_id and payload.emoji.name == "✅"):
			guild = self.get_guild(payload.guild_id)
			event_role = discord.utils.get(guild.roles, name=self.event_role_name)
			member = discord.utils.get(guild.members, id=payload.user_id)

			await member.add_roles(event_role)

	#Triggered when a reaction is removed from a message
	async def on_raw_reaction_remove(self, payload):
		#Do not trigger this function if the bot removes an emoji itself
		if(payload.member == self.user):
			return

		#In the future, must check if the event is still running.

		if(payload.message_id == self.last_event_message_id and payload.emoji.name == "✅"):
			guild = self.get_guild(payload.guild_id)
			event_role = discord.utils.get(guild.roles, name=self.event_role_name)
			member = discord.utils.get(guild.members, id=payload.user_id)

			await member.remove_roles(event_role)



if(__name__ == "__main__"):

	bot = Bot()
	#Get token from file to avoid leak
	with open('token/token.txt', 'r') as file:
		token = file.read()
	bot.run(token)
