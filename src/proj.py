# #All the required packages are imported.
# tweepy to access the twitter.
import tweepy
import json
import sys
import jsonpickle

# MySQLdb to access the MySQL database to store and retrive data.
import MySQLdb as db
from textblob import TextBlob
import warnings

# imdb to fetch the movie rating from the IMDB.
from imdb import IMDb
import sentiment_mod as senti


warnings.filterwarnings('ignore')

# This function is to load all the credentials to run this project.
# The file properties hold the access tokens for twitter and database information to connect and access.
def readPropertyFile():
	with open('properties','r') as f:
		auth = json.load(f)
		return auth

# On call to this function, it will reach twitter server to get the access object.
# Access tokens are passed to get the access from the twitter
def getAuth():
	auth = tweepy.AppAuthHandler(propertie['consumer_key'], propertie['consumer_secret'])
	api = tweepy.API(auth, wait_on_rate_limit=True,
				   wait_on_rate_limit_notify=True)
	if (not api):
		print ("Can't Authenticate")
		sys.exit(-1)
	return api

# This function is called to save movie related information into the database.
# It will save all the calculated rating and metrix's for each movie.
def saveData(searchQuery,textblobRating, nltkRating, imdbRating, nltkPos, nltkNeg, textblobPos, textblobNeg):
	cursor = conn.cursor();
	sql = "insert into movies(name,textblobRating,nltkRating,imdbRating,nltkPosCount,nltkNegCount,textblobPosCount,textblobNegCount) values(%s, %s, %s, %s, %s, %s, %s, %s)"
	number_of_rows = cursor.execute(sql, (searchQuery,textblobRating, nltkRating, imdbRating, nltkPos, nltkNeg, textblobPos, textblobNeg))
	conn.commit()
	return number_of_rows

# The search movie name is passed as argument for this function.
# Based on movie name, it will collect the tweets relating to that movie.
# This will download the collected tweets and save it in the database for later access.
# User can modify the total number of tweets that needs to be downloaded from twitter to determine the movie rating.
def searchTwitter(searchQuery):
	maxTweets = 1000 # Some arbitrary large number
	tweetsPerQry = 100  # this is the max the API permits


	# If results from a specific ID onwards are reqd, set since_id to that ID.
	# else default to no lower limit, go as far back as API allows
	sinceId = 0

	# If results only below a specific ID are, set max_id to that ID.
	# else default to no upper limit, start from the most recent tweet matching the search query.
	max_id = -1

	# It shotes the number of tweets that is collected so far in the downloading process,
	tweetCount = 0
	
	print("Downloading max {0} tweets".format(maxTweets))

	# This will loop keep collecting the tweets from the twitter untill collected tweets count reaches maxTweets.
	# This will scrap the tweets from the twitter by changing the since_id or max_id in the search query.
	# This is similar like accessing the data using start or end index.
	while tweetCount < maxTweets:
		tweetList = []
		try:
			if (max_id <= 0):
				if (not sinceId):
					new_tweets = api.search(q=searchQuery, count=tweetsPerQry,lang="en")
				else:
					new_tweets = api.search(q=searchQuery, count=tweetsPerQry,
					since_id=sinceId,lang="en")
			else:
				if (not sinceId):
					new_tweets = api.search(q=searchQuery, count=tweetsPerQry,
					max_id=str(max_id - 1),lang="en")
				else:
					new_tweets = api.search(q=searchQuery, count=tweetsPerQry,
					max_id=str(max_id - 1),
					since_id=sinceId,lang="en")
			if not new_tweets:
				print("No more tweets found")
				break
			print("...", end="")

			# For each query 100 tweets are collected. 
			for tweet in new_tweets:
				oneObj = tweet._json
				
				# A tweet is determined as qnique if it is not a re-tweet and it contains full data.
				# The tweets that satisfies this condition is only consideres and reset are discarded.
				if(oneObj["truncated"] == False and (not tweet.retweeted) and ('RT @' not in tweet.text)):
					tweetList.append(oneObj)

			# Save the accepted tweets into database for later processing.
			savedTweetCount = saveTweets(searchQuery, tweetList)
			tweetCount += savedTweetCount
			max_id = new_tweets[-1].id
		# Raise exception if there are any.
		except tweepy.TweepError as e:
			# Just exit if any error
			print("some error : " + str(e))
			break
	# Once the specified number of tweets are downloaded, now it is sent for processing to calculate the rating.
	textblobRating, nltkRating, nltkPos, nltkNeg, textblobPos, textblobNeg = processTweets(searchQuery)
	# Access the movie rating for that movie using IMDB api.
	imdbRating = getLatestMovieByNameFromIMDB(searchQuery)
	# Save the calculated rating into the database.
	insertedRows = saveData(searchQuery, textblobRating, nltkRating, imdbRating, nltkPos, nltkNeg, textblobPos, textblobNeg)
	print("Processing completed.....")
	
	
# Obtain the DB connection to using database configuartion in the properties file.
def dbConnection():
	conn = db.connect(host=propertie['db_host'],user=propertie['db_user'],passwd=propertie['db_passwd'],db=propertie['db_name'],use_unicode=True, charset="utf8");

	if(not conn):
		print ("DB Connection failed")
		sys.exit(-1)
	return conn

# Save each tweet into db table called tweets with repect to each movie.
def saveTweets(name, tweetList):
	data = []
	for eachTweet in tweetList:
		eachTweet = eachTweet
		data.append((name, eachTweet["id"], eachTweet["text"]))
	cursor = conn.cursor();
	sql = "insert ignore into tweets values(%s, %s, %s)"
	number_of_rows = cursor.executemany(sql, data)
	conn.commit()
	return number_of_rows

# Fetch the data from the database for given movie name.
# Since there is huge number of data, this function will fetch only chunk of data at once to reduct the memoty and bandwidth.
def getTweets(hashTag, offset, count):
	cursor = conn.cursor();
	sql = "select * from tweets where name=%s limit %s,%s"
	cursor.execute(sql, [hashTag,offset,count])
	data = cursor.fetchall()
	return data

# It will calculate the sentiment for each tweets using textblob
def calculateSentiment(tweet):
	testimonial = TextBlob(tweet)
	return testimonial.sentiment.polarity

# This will count the number of tweets that is already downloaded in the database
def getDBCount(searchQuery):
	cursor = conn.cursor();
	sql = "select count(1) as count from tweets where name=%s"
	cursor.execute(sql, [searchQuery])
	data = cursor.fetchall()
	return data[0][0]

# This will get the movie name. Using the name it will fetch the data stored in the database.
# It will process each tweets to determine the sentiment using textblob and nltk.
# For each tweets it will flag as positive or negative based on the sentiment.
# If the sentiment is is neutral then those tweets will be ignored.
# It also hold the positive and negative counts and calculate the rating based on the counts.
def processTweets(searchQuery):
	print("processing started...")
	count = 50
	offSet = 0
	posTweets = 0
	negTweets = 0
	nltkPos = 0
	nltkNeg = 0
	totalCount = getDBCount(searchQuery)
	cursor = conn.cursor();
	sql = "select count(1) from tweets where name=%s"
	cursor.execute(sql, [searchQuery])
	data = cursor.fetchall()

	while offSet < totalCount:
		tweets = getTweets(searchQuery, offSet, count);
		for each in tweets:
			polarity = round(calculateSentiment(each[2]),1)
			nltkRes = senti.sentiment(each[2])
			if(nltkRes):
				if(nltkRes[1] > 0.5):
					if(nltkRes[0] == "pos"):
						nltkPos += 1
					elif(nltkRes[0] == "neg"):
						nltkNeg += 1
			if(polarity > 0):
				posTweets += 1
			elif(polarity < 0):
				negTweets += 1
		offSet += count
	# print("positive: "+str(posTweets)+" negative"+str(negTweets))
	rating = (posTweets/(posTweets + negTweets))*10
	nltkRating = (nltkPos/(nltkPos + nltkNeg))*10
	return round(rating,1), round(nltkRating,1), nltkPos, nltkNeg, posTweets, negTweets

# Get access to the IMDB api
def getIMDB():
	imdb = IMDb()
	return imdb

# This function will fetch the rating of the movie in the IMDB.
# It will fetch the latest movie by the given name.
def getLatestMovieByNameFromIMDB(searchQuery):
	actual_movies = []
	id=0
	maxYear=0
	rating = 0
	try:
		movies = imdb.search_movie(searchQuery)

		for each in movies:
			if searchQuery.lower() == each["title"].lower():
				actual_movies.append((each.movieID,each["title"],each["year"]))

		print(actual_movies)
		for each in actual_movies:
			if each[2] > maxYear:
				maxYear = each[2]
				id = each[0].strip()
		print("id:",id)
		movie = imdb.get_movie(id)
		rating = movie["rating"]
	except Exception as e:
		print("Exception in fetching movie data",e)
	return rating

# This fucntion will return the query data for given movie name.
def getMovieFromDB(searchQuery):
	cursor = conn.cursor();
	sql = "select * from movies where name=%s"
	cursor.execute(sql, [searchQuery])
	data = cursor.fetchall()
	return data

# Load the propertt file
propertie = readPropertyFile()

# Get access to twitter api
api = getAuth()

# Get access to the MySQL DB
conn = dbConnection()

# Get access to the IMDB api
imdb = getIMDB()
