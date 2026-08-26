<?php
require 'cors.php';
require 'db.php';

header('Content-Type: application/json');
$input = json_decode(file_get_contents('php://input'), true);

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    echo json_encode(['success' => false, 'error' => 'Method not allowed']);
    exit;
}

$orderID = $input['orderID'] ?? '';
$tierID = $input['tierID'] ?? ''; // 1, 2, 3, 4
$userIdentifier = $input['userIdentifier'] ?? ''; // Email or Username (for new users) or UserID (future)
$isUpgrade = $input['isUpgrade'] ?? false; // If true, userIdentifier is likely a logged-in ID
$currentUserID = $input['userId'] ?? 0;

if (!$orderID || !$tierID) {
    echo json_encode(['success' => false, 'error' => 'Missing orderID or tierID']);
    exit;
}

// 1. Load Settings
$stmt = $pdo->query("SELECT * FROM settings");
$settings = [];
while ($row = $stmt->fetch()) {
    $settings[$row['setting_key']] = $row['setting_value'];
}
$clientId = $settings['paypal_client_id'] ?? '';
$secret = $settings['paypal_secret'] ?? '';
$mode = $settings['paypal_mode'] ?? 'sandbox';

if (!$clientId || !$secret) {
    echo json_encode(['success' => false, 'error' => 'Server Payment Config Missing']);
    exit;
}

// 2. Get Access Token from PayPal
$baseUrl = ($mode === 'live') ? 'https://api-m.paypal.com' : 'https://api-m.sandbox.paypal.com';
$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, "$baseUrl/v1/oauth2/token");
curl_setopt($ch, CURLOPT_HEADER, false);
curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true); 
curl_setopt($ch, CURLOPT_USERPWD, $clientId.":".$secret);
curl_setopt($ch, CURLOPT_POSTFIELDS, "grant_type=client_credentials");
$result = curl_exec($ch);
$json = json_decode($result, true);
$accessToken = $json['access_token'] ?? '';
curl_close($ch);

if (!$accessToken) {
    echo json_encode(['success' => false, 'error' => 'PayPal Auth Failed']);
    exit;
}

// 3. Verify Order Details
$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, "$baseUrl/v2/checkout/orders/$orderID");
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
curl_setopt($ch, CURLOPT_HTTPHEADER, array(
    "Content-Type: application/json",
    "Authorization: Bearer $accessToken"
));
$result = curl_exec($ch);
$order = json_decode($result, true);
curl_close($ch);

$status = $order['status'] ?? '';
if ($status !== 'COMPLETED' && $status !== 'APPROVED') {
    // If APPROVED, we might need to Capture it. For now assume Client captured it or we capture it here.
    // Simplifying: assumes Client flow sets it to completed or we trust APPROVED for simple flow?
    // STRICTLY: We should use Capture API if it's not completed.
    // For this implementation, we assume client side 'capture()' was called and we are verifying COMPLETED.
    // If status is APPROVED, let's try to capture it server side just in case.
    if ($status === 'APPROVED') {
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, "$baseUrl/v2/checkout/orders/$orderID/capture");
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_HTTPHEADER, array(
            "Content-Type: application/json",
            "Authorization: Bearer $accessToken"
        ));
        $captureResult = curl_exec($ch);
        $captureJson = json_decode($captureResult, true);
        curl_close($ch);
        $status = $captureJson['status'] ?? $status;
    }
}

if ($status !== 'COMPLETED') {
    echo json_encode(['success' => false, 'error' => 'Payment not completed: ' . $status]);
    exit; 
}

// 4. Payment Valid. Apply Upgrades.
$targetRole = '';
$days = 0;

if ($tierID == 1) { // Supporter
    $targetRole = 'ultra'; // Reward
    $days = $settings['donation_tier1_days'] ?? 7;
} elseif ($tierID == 2) { // Standard
    $targetRole = 'standard';
    $days = $settings['donation_tier2_days'] ?? 365;
} elseif ($tierID == 3) { // Pro
    $targetRole = 'pro';
    $days = $settings['donation_tier3_days'] ?? 365;
} elseif ($tierID == 4) { // Ultra
    $targetRole = 'ultra';
    $days = $settings['donation_tier4_days'] ?? 365;
}

// targetDate from now
$expiryDate = date('Y-m-d H:i:s', strtotime("+$days days"));

$userID = 0;

if ($currentUserID > 0) {
    // Upgrading existing logged in user
    $userID = $currentUserID;
    $stmt = $pdo->prepare("UPDATE users SET role = ?, expiry_date = ? WHERE id = ?");
    $stmt->execute([$targetRole, $expiryDate, $userID]);
} else {
    // Guest / New User by Email
    if (!$userIdentifier) {
        // Try to get email from PayPal payer info
        $payerEmail = $order['payer']['email_address'] ?? '';
        if ($payerEmail) {
            $userIdentifier = $payerEmail;
        } else {
            echo json_encode(['success' => false, 'error' => 'No email provided and cannot retrieve from PayPal']);
            exit; 
        }
    }

    // Check if user exists
    $stmt = $pdo->prepare("SELECT id FROM users WHERE username = ?");
    $stmt->execute([$userIdentifier]);
    $user = $stmt->fetch();

    if ($user) {
        $userID = $user['id'];
        $stmt = $pdo->prepare("UPDATE users SET role = ?, expiry_date = ? WHERE id = ?");
        $stmt->execute([$targetRole, $expiryDate, $userID]);
    } else {
        // Create new user
        // Generate random password
        $password = bin2hex(random_bytes(4)); // 8 chars
        $stmt = $pdo->prepare("INSERT INTO users (username, password, role, expiry_date) VALUES (?, ?, ?, ?)");
        $stmt->execute([$userIdentifier, $password, $targetRole, $expiryDate]);
        $userID = $pdo->lastInsertId();

        // Send Welcome Email (TODO: use settings template)
        // For now relying on the simple mail() or ignoring email logic for brevity of this step
        // We really should send the password!
        $subject = $settings['email_welcome_subject'] ?? 'Welcome';
        $body = $settings['email_welcome_body'] ?? 'Welcome {USERNAME}, Pass: {PASSWORD}';
        $body = str_replace('{USERNAME}', $userIdentifier, $body);
        $body = str_replace('{PASSWORD}', $password, $body);
        
        require_once 'mailer.php';
        sendRegistrationEmail($userIdentifier, $userIdentifier, $password);
    }
    
    // Send Notification of Donation/Upgrade (To User and Admin)
    // We need the amount.
    // PayPal Order Details has the amount.
    $amountValue = '0.00';
    try {
        if (isset($order['purchase_units'][0]['payments']['captures'][0]['amount']['value'])) {
             $amountValue = $order['purchase_units'][0]['payments']['captures'][0]['amount']['value'];
        } else if (isset($order['purchase_units'][0]['amount']['value'])) {
             $amountValue = $order['purchase_units'][0]['amount']['value'];
        }
    } catch (Exception $e) {}

    require_once 'mailer.php';
    sendDonationEmail($userIdentifier, $userIdentifier, $amountValue, $targetRole, $expiryDate);
}

echo json_encode(['success' => true, 'role' => $targetRole, 'expiry' => $expiryDate, 'days_added' => $days]);
?>
