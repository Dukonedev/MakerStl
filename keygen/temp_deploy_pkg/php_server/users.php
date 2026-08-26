<?php
ini_set('display_errors', 0);
ini_set('display_startup_errors', 0);
error_reporting(0);
require 'cors.php';
require 'db.php';

$method = $_SERVER['REQUEST_METHOD'];

// GET ALL USERS (Admin)
if ($method === 'GET') {
    $stmt = $pdo->query("SELECT id, username, role, created_at, download_count, expiry_date FROM users");
    $users = $stmt->fetchAll();
    echo json_encode(['success' => true, 'debug_version' => '1.5', 'users' => $users]);
}
// DELETE USER (Admin)
elseif ($method === 'POST' && isset($_GET['action'])) {
    $action = $_GET['action'];
    $data = json_decode(file_get_contents('php://input'), true);

    if ($action === 'delete') {
        $id = $data['id'] ?? 0;
        if ($id) {
            $stmt = $pdo->prepare("DELETE FROM users WHERE id = ?");
            $stmt->execute([$id]);
            echo json_encode(['success' => true]);
        } else {
            echo json_encode(['success' => false, 'error' => 'Missing ID']);
        }
    }
    elseif ($action === 'create') {
        $username = $data['username'] ?? '';
        $password = $data['password'] ?? '';
        $role = $data['role'] ?? 'user';

        if (!$username || !$password) {
             echo json_encode(['success' => false, 'error' => 'Missing username or password']);
             exit;
        }

        $hashed = password_hash($password, PASSWORD_BCRYPT);
        $expiry = date('Y-m-d H:i:s', strtotime('+1 year'));
        try {
            $stmt = $pdo->prepare("INSERT INTO users (username, password, role, expiry_date) VALUES (?, ?, ?, ?)");
            $stmt->execute([$username, $hashed, $role, $expiry]);
            echo json_encode(['success' => true]);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'error' => 'Username already exists']);
        }
    }
    elseif ($action === 'update_role') {
        $id = $data['id'] ?? 0;
        $role = $data['role'] ?? '';
        
        if (!$id || !$role) {
            echo json_encode(['success' => false, 'error' => 'Missing ID or Role']);
            exit;
        }

        try {
            $stmt = $pdo->prepare("UPDATE users SET role = ? WHERE id = ?");
            $stmt->execute([$role, $id]);
            echo json_encode(['success' => true]);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'error' => 'Database error: ' . $e->getMessage()]);
        }
    }
    elseif ($action === 'update_date') {
        $id = $data['id'] ?? 0;
        $date = $data['date'] ?? '';
        
        if (!$id || !$date) {
            echo json_encode(['success' => false, 'error' => 'Missing ID or Date']);
            exit;
        }

        try {
            $stmt = $pdo->prepare("UPDATE users SET created_at = ? WHERE id = ?");
            $stmt->execute([$date, $id]);
            echo json_encode(['success' => true]);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'error' => 'Database error: ' . $e->getMessage()]);
        }
    }
    elseif ($action === 'update_expiry') {
        $id = $data['id'] ?? 0;
        $expiry = $data['expiry'] ?? '';
        
        if (!$id || !$expiry) {
            echo json_encode(['success' => false, 'error' => 'Missing ID or Expiry Date']);
            exit;
        }

        try {
            $stmt = $pdo->prepare("UPDATE users SET expiry_date = ? WHERE id = ?");
            $stmt->execute([$expiry, $id]);
            echo json_encode(['success' => true]);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'error' => 'Database error: ' . $e->getMessage()]);
        }
    } else {
        echo json_encode(['success' => false, 'error' => 'Invalid Action: ' . $action]);
    }
} else {
    // Catch-all for POST without action or other methods
    if ($method === 'POST') {
         echo json_encode(['success' => false, 'error' => 'No action specified']);
    }
}
?>
