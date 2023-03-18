import mysql.connector

class Database:
	def __init__(self, host, username, password):
		self.username = username
		self.password = password
		self.host = host
		self.database_name = "ctfs"

		#Instances de la connexion et du curseur 
		self.db_connection = ""
		self.db_cursor = ""

#-----------------------------------------------------------------------------------------------------------------------------------------------------
#CONFIGURATION BDD

	#Connexion à mysql
	def connection(self, database_name):
		db_connection = mysql.connector.connect(
			host=self.host,
			user=self.username,
			passwd=self.password,
			database=self.database_name
		)
		self.db_connection = db_connection
		return db_connection

	#Exécute une commande
	def execute_command(self, command, values=""):
		db_connection = self.connection(self.database_name)
		db_cursor = db_connection.cursor()
		db_cursor.execute(command, values)
		#On stocke le résultat de la commande
		self.db_cursor = db_cursor

	#Connexion à la bdd
	def use_database(self):
		self.execute_command("USE " + '`' + self.database_name + '`')

	def show_all_tables(self):
		self.execute_command("SHOW tables")
		tables = self.db_cursor.fetchall()
		return tables


#-----------------------------------------------------------------------------------------------------------------------------------------------------
#users

	def insert_into_users(self, discord_id, points):
		values = [discord_id, points]
		self.execute_command("INSERT INTO users(discord_id, points) VALUES(%s, %s)", values)
		self.db_connection.commit()

	# def delete_user(self, discord_id):
	# 	self.execute_command(" DELETE FROM users WHERE discord_id='" + str(discord_id) + "'")
	# 	self.db_connection.commit()

	# def get_all_users(self):
	# 	self.use_database()
	# 	self.execute_command("SELECT * FROM users")
	# 	return self.db_cursor.fetchall()

	def get_all_users_asc(self):
		self.use_database()
		self.execute_command("SELECT * FROM users ORDER BY points DESC")
		return self.db_cursor.fetchall()

	def get_user_rank_leaderboard(self, discord_id):
		self.use_database()
		self.execute_command("SELECT COUNT(*) AS user_rank FROM (SELECT u.discord_id, u.points FROM users u ORDER BY points DESC) users_rank WHERE points > (SELECT points FROM users WHERE discord_id = '" + str(discord_id) + "') OR (points = (SELECT points FROM users WHERE discord_id = '" + str(discord_id) + "') AND discord_id <= '" + str(discord_id) + "')")
		return self.db_cursor.fetchall()

	def update_user(self, discord_id, points):
		self.execute_command("UPDATE users SET points = points + '" + str(points) + "' WHERE discord_id = '" + str(discord_id) + "'")
		self.db_connection.commit()

	def get_user_by_id(self, discord_id):
		self.use_database()
		self.execute_command("SELECT * FROM users WHERE discord_id = '" + str(discord_id) + "'")
		return self.db_cursor.fetchall()

	def get_user_number_participations(self, discord_id):
		self.use_database()
		self.execute_command("SELECT COUNT(DISTINCT event_id) AS participation_count FROM submissions WHERE discord_id = '" + str(discord_id) + "'")
		return self.db_cursor.fetchall()

	def get_user_number_flags_submitted(self, discord_id):
		self.use_database()
		self.execute_command("SELECT COUNT(*) AS total_flags_submit FROM submissions WHERE discord_id = '" + str(discord_id) + "'")
		return self.db_cursor.fetchall()

	def get_user_number_correct_flags(self, discord_id):
		self.use_database()
		self.execute_command("SELECT COUNT(DISTINCT s.hash) AS correct_flags_count FROM submissions s INNER JOIN flags f ON s.hash = f.hash AND s.event_id = f.event_id WHERE s.discord_id = '" + str(discord_id) + "' AND s.hash = f.hash")
		return self.db_cursor.fetchall()

	def get_user_number_first_bloods(self, discord_id):
		self.use_database()
		self.execute_command("SELECT COUNT(*) as first_bloods_count FROM (SELECT s1.discord_id, f.name, s1.date FROM submissions s1 INNER JOIN flags f ON s1.hash = f.hash INNER JOIN (SELECT event_id, hash, MIN(date) AS min_date FROM submissions WHERE hash IN (SELECT hash FROM flags) GROUP BY event_id, hash) s2 ON s1.event_id = s2.event_id AND s1.hash = s2.hash AND s1.date = s2.min_date WHERE s1.discord_id = '" + str(discord_id) + "') s GROUP BY s.discord_id")
		return self.db_cursor.fetchall()	

	def get_points_user(self, discord_id):
		self.use_database()
		self.execute_command("SELECT points FROM users WHERE discord_id='" + str(discord_id) + "'")

		points = self.db_cursor.fetchall()
		return points[0][0]


#-------------------------------------------------------------------------------------------->
#events

	#Used when creating a new event
	def insert_into_events(self, name, description, url, number_of_flags, starting_date, ending_date):
		values = [name, description, url, number_of_flags, starting_date, ending_date]
		self.execute_command("INSERT INTO events(name, description, url, number_of_flags, starting_date, ending_date) VALUES(%s, %s, %s, %s, %s, %s)", values)
		self.db_connection.commit()
		#Return the last inserted object
		return self.db_cursor.lastrowid

	# def delete_event_by_id(self, event_id):
	# 	self.use_database()
	# 	self.execute_command(" DELETE FROM events WHERE event_id='" + str(event_id) + "'")
	# 	self.db_connection.commit()

	def get_all_events_by_state(self, state):
		self.use_database()
		self.execute_command("SELECT * FROM events WHERE state = '" + str(state) + "'")
		return self.db_cursor.fetchall()

	def get_event_by_id(self, event_id):
		self.use_database()
		self.execute_command("SELECT * FROM events WHERE event_id = '" + str(event_id) + "'")
		return self.db_cursor.fetchall()

	def get_event_by_state_and_id(self, state, event_id):
		self.use_database()
		self.execute_command("SELECT * FROM events WHERE state = '" + str(state) + "' AND event_id = '" + str(event_id) + "'")
		return self.db_cursor.fetchall()

	# def get_all_events(self):
	# 	self.use_database()
	# 	self.execute_command("SELECT * FROM events")
	# 	return self.db_cursor.fetchall()

	def get_event_number_participants(self, event_id):
		self.use_database()
		self.execute_command("SELECT count(DISTINCT discord_id) FROM submissions WHERE event_id = '" + str(event_id) + "'")
		return self.db_cursor.fetchall()

	def get_all_events_where_user_participated(self, discord_id):
		self.use_database()
		self.execute_command("SELECT DISTINCT e.* FROM events e INNER JOIN submissions s ON e.event_id = s.event_id WHERE s.discord_id = '" + str(discord_id) + "' ORDER BY e.starting_date DESC")
		return self.db_cursor.fetchall()

	def update_event_state(self, event_id, state):
		self.execute_command("UPDATE events SET state = '" + str(state) + "' WHERE event_id = '" + str(event_id) + "'")
		self.db_connection.commit()

	# def update_event_ending_date(self, event_id, ending_date):
	# 	self.execute_command("UPDATE events SET ending_date = '" + str(ending_date) + "' WHERE name = '" + str(name) + "'")
	# 	self.db_connection.commit()

	def update_event_difficulty(self, event_id, difficulty):
		self.execute_command("UPDATE events SET difficulty = '" + str(difficulty) + "' WHERE event_id = '" + str(event_id) + "'")
		self.db_connection.commit()

#---------------------------------------------------------------------------------------------------------------------------
#submissions

	def insert_into_submissions(self, discord_id, event_id, hash_str, date):
		values = [discord_id, event_id, hash_str, date]
		self.execute_command("INSERT INTO submissions(discord_id, event_id, hash, date) VALUES(%s, %s, %s, %s)", values)
		self.db_connection.commit()


	def get_user_submissions(self, discord_id, event_id):
		self.use_database()
		self.execute_command("SELECT * FROM submissions WHERE discord_id = '" + str(discord_id) + "' AND event_id = '" + str(event_id) + "'")
		return self.db_cursor.fetchall()

	#For this version, we give the flag
	def get_correct_submissions_by_event_id(self, event_id, flag):
		self.use_database()
		self.execute_command("SELECT * FROM submissions WHERE event_id = '" + str(event_id) + "' AND hash = '" + str(flag) + "'")
		return self.db_cursor.fetchall()

	def count_correct_submissions_by_event_id(self, event_id):
		self.use_database()
		self.execute_command("SELECT COUNT(*) FROM submissions, flags WHERE flags.event_id = '" + str(event_id) + "' AND flags.event_id = submissions.event_id AND flags.hash = submissions.hash")
		return self.db_cursor.fetchall()

	#Return a list of users id (first column) that have at least one correct flag for the specific event. Also returns the number of correct flags each user has (column 2)
	#Order by the users that have the most correct flags for the event and then order by date (first submission on top)
	#Error by default with this request. In MySQL, must deactivate the full_group_by mode -> sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf -> sql_mode = "STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION" -> sudo systemctl restart mysql 
	def get_users_correct_submissions_by_event_id(self, event_id):
		self.use_database()
		self.execute_command("SELECT s.discord_id, COUNT(DISTINCT s.hash) AS correct_flags, MIN(s.date) AS first_submission_date FROM submissions s INNER JOIN flags f ON f.event_id = s.event_id AND f.hash = s.hash WHERE f.event_id = '" + str(event_id) + "' GROUP BY s.discord_id HAVING correct_flags > 0 ORDER BY correct_flags DESC, first_submission_date ASC;")
		return self.db_cursor.fetchall()

	def get_users_first_bloods_by_event_id(self, event_id):
		self.use_database()
		self.execute_command("SELECT s1.discord_id, f.name, s1.date FROM submissions s1 INNER JOIN flags f ON s1.hash = f.hash INNER JOIN (SELECT event_id, hash, MIN(date) AS min_date FROM submissions WHERE hash IN (SELECT hash FROM flags WHERE event_id = '" + str(event_id) + "') GROUP BY event_id, hash) s2 ON s1.event_id = s2.event_id AND s1.hash = s2.hash AND s1.date = s2.min_date WHERE s1.hash IN (SELECT hash FROM flags WHERE event_id = '" + str(event_id) + "') ORDER BY s1.event_id, s1.date")
		return self.db_cursor.fetchall()
	
	def get_fastest_users_to_complete_event(self, event_id, limit):
		self.use_database()
		self.execute_command("SELECT submissions.discord_id, MAX(submissions.date) AS completion_date FROM submissions JOIN (SELECT event_id, starting_date FROM events WHERE event_id = '" + str(event_id) + "') AS event_info ON submissions.event_id = event_info.event_id JOIN flags ON flags.event_id = submissions.event_id AND flags.hash = submissions.hash WHERE submissions.date >= event_info.starting_date GROUP BY submissions.discord_id HAVING COUNT(DISTINCT flags.hash) = (SELECT COUNT(*) FROM flags WHERE event_id = '" + str(event_id) + "') ORDER BY completion_date ASC LIMIT " + str(limit))
		return self.db_cursor.fetchall()

	def get_number_submissions_by_event_id(self, event_id):
		self.use_database()
		self.execute_command("SELECT COUNT(*) FROM submissions WHERE event_id = '" + str(event_id) + "'")
		return self.db_cursor.fetchall()

	def delete_submissions_by_event_id(self, event_id):
		self.use_database()
		self.execute_command(" DELETE FROM submissions WHERE event_id='" + str(event_id) + "'")
		self.db_connection.commit()


#---------------------------------------------------------------------------------------------------------------------------
#votes

	def insert_into_votes(self, discord_id, event_id, note):
		values = [discord_id, event_id, note]
		self.execute_command("INSERT INTO votes(discord_id, event_id, note) VALUES(%s, %s, %s)", values)
		self.db_connection.commit()
		#Return the last inserted object
		return self.db_cursor.lastrowid

	def get_all_votes_by_event_and_user(self, discord_id, event_id):
		self.use_database()
		self.execute_command("SELECT * FROM votes WHERE discord_id = '" + str(discord_id) + "' AND event_id = '" + str(event_id) + "'")
		return self.db_cursor.fetchall()

	def get_all_votes_by_event(self, event_id):
		self.use_database()
		self.execute_command("SELECT * FROM votes WHERE event_id = '" + str(event_id) + "'")
		return self.db_cursor.fetchall()

	def delete_votes_by_event_id(self, event_id):
		self.use_database()
		self.execute_command(" DELETE FROM votes WHERE event_id='" + str(event_id) + "'")
		self.db_connection.commit()


#-------------------------------------------------------------------------------------------->
#flags

	def insert_into_flags(self, name, event_id, hash):
		values = [name, event_id, hash]
		self.execute_command("INSERT INTO flags(name, event_id, hash) VALUES(%s, %s, %s)", values)
		self.db_connection.commit()
		#Return the last inserted object
		return self.db_cursor.lastrowid

	def get_all_flags_by_event_id(self, event_id):
		self.use_database()
		self.execute_command("SELECT * FROM flags WHERE event_id = '" + str(event_id) + "'")
		return self.db_cursor.fetchall()

	def get_flag_by_event_and_name(self, event_id, name):
		self.use_database()
		self.execute_command("SELECT * FROM flags WHERE event_id = '" + str(event_id) + "' AND name = '" + str(name) + "'")
		return self.db_cursor.fetchall()

	def update_flag_hash(self, name, event_id, hash):
		self.execute_command("UPDATE flags SET hash = '" + str(hash) + "' WHERE event_id = '" + str(event_id) + "' AND name = '" + str(name) + "'")
		self.db_connection.commit()

#-----------------------------------------------------------------------------------------------------------------------------------------------------
#MAIN TEST

if __name__ == "__main__":

	db = Database("localhost", "discord_bot_user", "discord_bot_user")
