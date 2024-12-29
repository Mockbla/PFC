-- MySQL dump 10.13  Distrib 8.0.38, for Win64 (x86_64)
--
-- Host: localhost    Database: ged
-- ------------------------------------------------------
-- Server version	8.0.39

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `post`
--

DROP TABLE IF EXISTS `post`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `post` (
  `id` int NOT NULL AUTO_INCREMENT,
  `listId` int NOT NULL,
  `postTimestamp` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `rev` varchar(45) NOT NULL,
  `rejectTimestamp` datetime DEFAULT NULL,
  `title` text,
  `filename` varchar(255) NOT NULL,
  `folder` varchar(255) NOT NULL,
  `userId` int NOT NULL,
  `managerApproval` tinyint(1) DEFAULT NULL,
  `managerApprovalTimestamp` timestamp NULL DEFAULT NULL,
  `archiveApproval` tinyint(1) DEFAULT NULL,
  `archiveApprovalTimestamp` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `post`
--

LOCK TABLES `post` WRITE;
/*!40000 ALTER TABLE `post` DISABLE KEYS */;
INSERT INTO `post` VALUES (6,61,'2024-12-23 15:48:54','A',NULL,'PROJETO MECÂNICO Sistema de Transporte de Minério Correia Transportadora Principal - Linha 03','PFC_Guilherme_Avelar-1-30Coment.pdf','d1ab2362-2ac4-4741-bd95-29f7749a3a6d',1,1,'2024-12-23 18:49:34',1,'2024-12-23 18:49:49'),(7,61,'2024-12-23 15:56:27','B',NULL,'PROJETO MECÂNICO Sistema de Transporte de Minério Correia Transportadora Principal - Linha 02','TCCE_GA_EaD_2017_LOPES_ANA.pdf','bb131a25-f5dd-446e-9059-c89e081c6d37',1,NULL,NULL,NULL,NULL),(8,64,'2024-12-25 10:19:25','A',NULL,'PROJETO MECÂNICO\r\nSistema de Transporte de Minério\r\nCorreia Transportadora Principal - Linha 01','DG-0001-0B-CO-B0-00B3_Rev_A.pdf','ed887954-2d4b-4966-ba42-e33b53d4d826',1,1,'2024-12-25 13:22:12',1,'2024-12-25 13:23:00');
/*!40000 ALTER TABLE `post` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2024-12-29 18:27:41
