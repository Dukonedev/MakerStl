<?php
require 'cors.php';
require 'db.php';

$action = $_GET['action'] ?? '';
$data = json_decode(file_get_contents('php://input'), true);

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    // GET GLOBAL STATS
    try {
        $stmt1 = $pdo->query("SELECT SUM(download_count) as total FROM users");
        $row1 = $stmt1->fetch();
        $totalDownloads = $row1['total'] ?? 0;

        $stmt2 = $pdo->query("SELECT COUNT(*) as total FROM users");
        $totalUsers = $stmt2->fetchColumn() ?: 0;

        echo json_encode([
            'success' => true,
            'total_downloads' => (int)$totalDownloads,
            'total_users' => (int)$totalUsers
        ]);
    } catch (PDOException $e) {
        echo json_encode(['success' => false, 'error' => $e->getMessage()]);
    }
} elseif ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Track Download
    if ($action === 'track') {
        $user_id = $data['user_id'] ?? 0;
        if ($user_id) {
            try {
                $stmt = $pdo->prepare("UPDATE users SET download_count = download_count + 1 WHERE id = ?");
                $stmt->execute([$user_id]);
                
                // Return updated count for this user
                $stmt = $pdo->prepare("SELECT download_count FROM users WHERE id = ?");
                $stmt->execute([$user_id]);
                $user = $stmt->fetch();
                
                echo json_encode(['success' => true, 'download_count' => (int)$user['download_count']]);
            } catch (PDOException $e) {
                echo json_encode(['success' => false, 'error' => $e->getMessage()]);
            }
        } else {
            echo json_encode(['success' => false, 'error' => 'Missing User ID']);
        }
    }
}
?>
