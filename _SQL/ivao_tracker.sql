SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET AUTOCOMMIT = 0;
START TRANSACTION;
SET time_zone = "+00:00";

CREATE TABLE `atcs` (
  `id` int(11) NOT NULL,
  `callsign` varchar(20) NOT NULL,
  `vid` int(11) NOT NULL,
  `status` varchar(20) NOT NULL,
  `rating` varchar(10) NOT NULL,
  `latitude` float NOT NULL,
  `longitude` float NOT NULL,
  `server` varchar(20) NOT NULL,
  `protocol` varchar(10) NOT NULL,
  `software` varchar(20) NOT NULL,
  `frequency` float NOT NULL,
  `radar_range` int(11) NOT NULL,
  `atis` text NOT NULL,
  `atis_time` datetime NOT NULL,
  `online` tinyint(1) NOT NULL,
  `connected_at` datetime NOT NULL,
  `disconnected_at` datetime DEFAULT NULL,
  `last_tracked_at` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `pilots` (
  `id` int(11) NOT NULL,
  `callsign` varchar(20) NOT NULL,
  `vid` int(11) NOT NULL,
  `status` varchar(20) NOT NULL,
  `rating` varchar(10) NOT NULL,
  `latitude` float NOT NULL,
  `longitude` float NOT NULL,
  `server` varchar(20) NOT NULL,
  `protocol` varchar(10) NOT NULL,
  `software` varchar(20) NOT NULL,
  `heading` int(11) NOT NULL,
  `on_ground` tinyint(1) NOT NULL,
  `altitude` int(11) NOT NULL,
  `groundspeed` int(11) NOT NULL,
  `mode_a` int(11) NOT NULL,
  `fp_aircraft` varchar(30) NOT NULL,
  `fp_speed` varchar(10) NOT NULL,
  `fp_rfl` varchar(10) NOT NULL,
  `fp_departure` varchar(4) NOT NULL,
  `fp_destination` varchar(4) NOT NULL,
  `fp_alternate` varchar(4) NOT NULL,
  `fp_alternate2` varchar(4) NOT NULL,
  `fp_type` varchar(5) NOT NULL,
  `fp_pob` int(11) NOT NULL,
  `fp_route` text NOT NULL,
  `fp_item18` text NOT NULL,
  `fp_rev` int(11) NOT NULL,
  `fp_rule` varchar(5) NOT NULL,
  `fp_deptime` varchar(10) NOT NULL,
  `fp_eet` int(11) NOT NULL,
  `fp_endurance` int(11) NOT NULL,
  `sim_type` varchar(50) NOT NULL,
  `online` tinyint(1) NOT NULL,
  `connected_at` datetime NOT NULL,
  `disconnected_at` datetime DEFAULT NULL,
  `last_tracked_at` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `pilot_positions` (
  `id` int(11) NOT NULL,
  `session_id` int(11) NOT NULL,
  `latitude` float NOT NULL,
  `longitude` float NOT NULL,
  `altitude` int(11) NOT NULL,
  `heading` int(11) NOT NULL,
  `on_ground` tinyint(1) NOT NULL,
  `groundspeed` int(11) NOT NULL,
  `tracked_at` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


ALTER TABLE `atcs`
  ADD PRIMARY KEY (`id`),
  ADD KEY `callsign` (`callsign`),
  ADD KEY `vid` (`vid`),
  ADD KEY `online` (`online`);

ALTER TABLE `pilots`
  ADD PRIMARY KEY (`id`),
  ADD KEY `fp_departure` (`fp_departure`),
  ADD KEY `fp_destination` (`fp_destination`),
  ADD KEY `online` (`online`),
  ADD KEY `callsign` (`callsign`),
  ADD KEY `vid` (`vid`);

ALTER TABLE `pilot_positions`
  ADD PRIMARY KEY (`id`),
  ADD KEY `session_id` (`session_id`);


ALTER TABLE `atcs`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `pilots`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `pilot_positions`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;
COMMIT;
