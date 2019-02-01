
--create database using below query
create database smdm;

--use the database using below query
use smdm;

--create table called tweets using below query which store tweets
CREATE TABLE `tweets` (
  `name` varchar(255) NOT NULL,
  `id` varchar(255) NOT NULL,
  `description` varchar(1024) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `description` (`description`)
);


--create table called movies using below query which movie rating
CREATE TABLE `movies` (
  `name` varchar(255) NOT NULL,
  `textblobRating` float NOT NULL,
  `nltkRating` float NOT NULL,
  `imdbRating` float NOT NULL,
  `rottenTomatoesRating` float DEFAULT '0',
  `nltkPosCount` int(11) NOT NULL,
  `nltkNegCount` int(11) NOT NULL,
  `textblobPosCount` int(11) NOT NULL,
  `textblobNegCount` int(11) NOT NULL,
  PRIMARY KEY (`name`)
);