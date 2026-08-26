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

    // SETTINGS TABLE
    $pdo->exec("CREATE TABLE IF NOT EXISTS settings (
        setting_key VARCHAR(50) PRIMARY KEY,
        setting_value TEXT
    )");

    // Seed Default Settings if table is empty
    $stmt = $pdo->query("SELECT COUNT(*) FROM settings");
    if ($stmt->fetchColumn() == 0) {
        $defaults = [
            'smtp_host' => 'mail.tophost.it',
            'smtp_port' => '587',
            'smtp_user' => 'virtuprinto.com77298',
            'smtp_pass' => 'xQ5+vQd65x',
            'smtp_from_email' => 'keygen3d@virtuprinto.com',
            'smtp_from_name' => 'Keygen3d',
            'admin_email' => 'keygen3d@virtuprinto.com',
            
            // Templates
            'email_welcome_subject' => 'Welcome to Keygen3d!',
            'email_welcome_body' => "
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; background-color: #000; color: #ddd; padding: 20px; }
        .container { background-color: #111; border: 1px solid #333; padding: 20px; border-radius: 10px; }
        h1 { color: #a3e635; }
        strong { color: #fff; }
        .creds { background: #222; padding: 15px; border-left: 3px solid #a3e635; margin: 20px 0; }
        .footer { margin-top: 20px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class='container'>
        <h1>Welcome, {USERNAME}!</h1>
        <p>Thank you for registering with Keygen 3D.</p>
        
        <div class='creds'>
            <strong>Your Credentials:</strong><br>
            Username: {USERNAME}<br>
            Password: {PASSWORD}
        </div>

        <p>Your account is active and valid for <strong>1 Year</strong>.</p>
        
        <div class='footer'>
            Keygen 3D - Design & Print System<br>
            Automated Message
        </div>
    </div>
</body>
</html>",
            'email_reset_subject' => 'Keygen 3D - Password Reset',
            'email_reset_body' => "
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; background-color: #000; color: #ddd; padding: 20px; }
        .container { background-color: #111; border: 1px solid #333; padding: 20px; border-radius: 10px; }
        h1 { color: #a3e635; }
        strong { color: #fff; }
        .creds { background: #222; padding: 15px; border-left: 3px solid #a3e635; margin: 20px 0; }
        .footer { margin-top: 20px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class='container'>
        <h1>Password Reset</h1>
        <p>You requested a password reset for Keygen 3D.</p>
        
        <div class='creds'>
            <strong>New Password:</strong><br>
            {PASSWORD}
        </div>

        <p>Please log in with this password immediately. You cannot change it manually, so keep this email safe.</p>
        
        <div class='footer'>
            If you did not request this, please contact support.
        </div>
    </div>
</body>
</html>"
        ];

        $insert = $pdo->prepare("INSERT INTO settings (setting_key, setting_value) VALUES (?, ?)");
        foreach ($defaults as $key => $value) {
            $insert->execute([$key, $value]);
        }
        echo "Settings seeded. ";
    }

} catch (PDOException $e) {
    echo json_encode(['error' => $e->getMessage()]);
}
?>
