<?php
require 'cors.php';
require 'db.php';

$action = $_GET['action'] ?? '';
$data = json_decode(file_get_contents('php://input'), true);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // LOGIN
    if ($action === 'login') {
        $username = $data['username'] ?? '';
        $password = $data['password'] ?? '';

        $stmt = $pdo->prepare("SELECT * FROM users WHERE username = ?");
        $stmt->execute([$username]);
        $user = $stmt->fetch();

        if ($user && password_verify($password, $user['password'])) {
            unset($user['password']); // Don't send hash back
            echo json_encode(['success' => true, 'user' => $user]);
        } else {
            echo json_encode(['success' => false, 'error' => 'Invalid credentials']);
        }
    }
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
            echo json_encode(['success' => true]);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'error' => 'Username already exists']);
        }
    }
}
?>
