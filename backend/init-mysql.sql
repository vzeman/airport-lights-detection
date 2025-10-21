-- Grant privileges to the airport_user from any host
GRANT ALL PRIVILEGES ON airport_mgmt.* TO 'airport_user'@'%';
FLUSH PRIVILEGES;

-- Additional configuration for Docker networking
CREATE USER IF NOT EXISTS 'airport_user'@'172.%' IDENTIFIED BY 'airport_pass';
GRANT ALL PRIVILEGES ON airport_mgmt.* TO 'airport_user'@'172.%';

CREATE USER IF NOT EXISTS 'airport_user'@'192.168.%' IDENTIFIED BY 'airport_pass';
GRANT ALL PRIVILEGES ON airport_mgmt.* TO 'airport_user'@'192.168.%';

FLUSH PRIVILEGES;