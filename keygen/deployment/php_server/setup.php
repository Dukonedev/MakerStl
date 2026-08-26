<?php
require 'cors.php';
require 'db.php';

try {
    $sql = "CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL,
        role VARCHAR(50) DEFAULT 'user',
        download_count INT DEFAULT 0,
        expiry_date DATETIME,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )";
    $pdo->exec($sql);

    // Migration: Add expiry_date if missing
    try {
        $pdo->exec("ALTER TABLE users ADD COLUMN expiry_date DATETIME AFTER download_count");
        echo "Migration: expiry_date column added. ";
        // Initialize expiry_date for existing users to 1 year after created_at
        $pdo->exec("UPDATE users SET expiry_date = DATE_ADD(created_at, INTERVAL 1 YEAR) WHERE expiry_date IS NULL");
        echo "Migration: expiry_date initialized for existing users. ";
    } catch (PDOException $e) {
        if ($e->getCode() == '42S21') {
             // Already exists
        } else {
            echo "Migration Notice: " . $e->getMessage();
        }
    }

    // Seed Admin
    $stmt = $pdo->prepare("SELECT * FROM users WHERE username = ?");
    $stmt->execute(['admin']);
    if (!$stmt->fetch()) {
        $pass = password_hash('Giuli@', PASSWORD_BCRYPT);
        $expiry = date('Y-m-d H:i:s', strtotime('+1 year')); // Set expiry for admin
        $stmt = $pdo->prepare("INSERT INTO users (username, password, role, expiry_date) VALUES (?, ?, ?, ?)");
        $stmt->execute(['admin', $pass, 'admin', $expiry]);
        echo json_encode(['message' => 'Table created and Admin seeded. ']);
    } else {
        echo json_encode(['message' => 'Table exists. Admin already exists. ']);
    }

    // Migration: Add download_count if missing
    try {
        $pdo->exec("ALTER TABLE users ADD COLUMN download_count INT DEFAULT 0 AFTER role");
        echo "Migration: download_count column added.";
    } catch (PDOException $e) {
        // Ignore if column already exists
        if ($e->getCode() == '42S21') {
             // Column already exists, ignore
        } else {
            echo "Migration Notice: " . $e->getMessage();
        }
    }

} catch (PDOException $e) {
    echo json_encode(['error' => $e->getMessage()]);
}
?>
