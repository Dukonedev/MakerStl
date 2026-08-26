<?php
ob_start();
require 'cors.php';
require 'db.php';

$action = $_GET['action'] ?? '';
$data = json_decode(file_get_contents('php://input'), true);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // REGISTER
    elseif ($action === 'register') {
        $username = $data['username'] ?? '';
        $password = $data['password'] ?? '';
        $role = $data['role'] ?? 'user';

        // Hash password
        $hashed = password_hash($password, PASSWORD_BCRYPT);
        $expiry = date('Y-m-d H:i:s', strtotime('+1 year'));

        try {
            $stmt = $pdo->prepare("INSERT INTO users (username, password, role, expiry_date) VALUES (?, ?, ?, ?)");
            $stmt->execute([$username, $hashed, $role, $expiry]);

            // SEND EMAIL NOTIFICATION (with its own buffering)
            try {
                ob_start();
                require_once 'mailer.php';
                sendRegistrationEmail($username, $username, $password);
                ob_end_clean();
            } catch (Exception $e) {
                error_log("Email trigger failed: " . $e->getMessage());
                if (ob_get_level()) ob_end_clean();
            }

            ob_clean(); // Clean any previous warnings
            echo json_encode(['success' => true]);
        } catch (PDOException $e) {
            ob_clean();
            echo json_encode(['success' => false, 'error' => 'Username already exists']);
        }
    }
    // FORGOT PASSWORD
    elseif ($action === 'forgot_password') {
        $username = $data['username'] ?? '';

        $stmt = $pdo->prepare("SELECT * FROM users WHERE username = ?");
        $stmt->execute([$username]);
        $user = $stmt->fetch();

        if ($user) {
            // Generate Random Password
            $newPassword = substr(str_shuffle("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"), 0, 8);
            $hashed = password_hash($newPassword, PASSWORD_BCRYPT);

            // Update DB
            $upd = $pdo->prepare("UPDATE users SET password = ? WHERE id = ?");
            $upd->execute([$hashed, $user['id']]);

            // Email User
            try {
                ob_start();
                require_once 'mailer.php';
                $sent = sendPasswordResetEmail($username, $newPassword);
                ob_end_clean();
                
                if ($sent) {
                    ob_clean();
                    echo json_encode(['success' => true]);
                } else {
                    ob_clean();
                    echo json_encode(['success' => false, 'error' => 'Failed to send email. Check logs.']);
                }
            } catch (Exception $e) {
                if (ob_get_level()) ob_end_clean();
                ob_clean();
                 echo json_encode(['success' => false, 'error' => 'Email error: ' . $e->getMessage()]);
            }
        } else {
            // Security: Don't reveal if user exists, but here we just error
             ob_clean();
             echo json_encode(['success' => false, 'error' => 'User not found']);
        }
    }
    
    // Fallback for LOGIN or others
    else {
         if ($action === 'login') {
            $username = $data['username'] ?? '';
            $password = $data['password'] ?? '';
    
            $stmt = $pdo->prepare("SELECT * FROM users WHERE username = ?");
            $stmt->execute([$username]);
            $user = $stmt->fetch();
    
            if ($user && password_verify($password, $user['password'])) {
                unset($user['password']); // Don't send hash back
                ob_clean();
                echo json_encode(['success' => true, 'user' => $user]);
            } else {
                ob_clean();
                echo json_encode(['success' => false, 'error' => 'Invalid credentials']);
            }
        }
    }
}
