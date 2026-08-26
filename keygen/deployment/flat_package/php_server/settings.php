<?php
require 'cors.php';
require 'db.php';

header('Content-Type: application/json');

$method = $_SERVER['REQUEST_METHOD'];

$defaults = [
    'smtp_host' => 'mail.tophost.it',
    'smtp_port' => '587',
    'smtp_user' => 'virtuprinto.com77298',
    'smtp_pass' => 'xQ5+vQd65x',
    'smtp_from_email' => 'keygen3d@virtuprinto.com',
    'smtp_from_name' => 'Keygen3d',
    'admin_email' => 'keygen3d@virtuprinto.com',
    'telegram_bot_token' => '',
    'telegram_chat_id' => '',
    
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
</html>",
    // Donation Notification Settings
    'email_donation_subject' => 'Thank You for your Support! - Keygen 3D',
    'email_donation_body' => "
<html>
<body>
<h1>Thank You, {USERNAME}!</h1>
<p>We received your donation/upgrade ({AMOUNT} EUR). Your support helps us keep building!</p>
<p>Your account has been upgraded to <strong>{ROLE}</strong> until <strong>{EXPIRY}</strong>.</p>
</body>
</html>",
    'email_admin_donation_subject' => '[ALERT] New Donation Received',
    'email_admin_donation_body' => "Donation received from {USERNAME} ({EMAIL}). Amount: {AMOUNT} EUR. Role: {ROLE}.",
    // Donation / Subscription Defaults
    'donation_tier1_title' => 'Sostenitore',
    'donation_tier1_desc' => 'Fai una donazione libera per sostenere il progetto. Ricompensa: 1 Settimana di accesso "Ultra".',
    'donation_tier1_price' => 'Donazione Libera',
    'donation_tier1_amount' => '0', // 0 = Free/Custom
    'donation_tier1_days' => '7',
    'donation_tier1_url' => '', // Deprecated in favor of API
    
    'donation_tier2_title' => 'Standard',
    'donation_tier2_desc' => 'Licenza valida 1 Anno. Funzionalità Standard per hobbyist.',
    'donation_tier2_price' => '20.00€',
    'donation_tier2_amount' => '20.00',
    'donation_tier2_days' => '365',
    'donation_tier2_url' => '',
    
    'donation_tier3_title' => 'Pro',
    'donation_tier3_desc' => 'Licenza valida 1 Anno. Font avanzati ed opzioni di export.',
    'donation_tier3_price' => '35.00€',
    'donation_tier3_amount' => '35.00',
    'donation_tier3_days' => '365',
    'donation_tier3_url' => '',
    
    'donation_tier4_title' => 'Ultra',
    'donation_tier4_desc' => 'Licenza valida 1 Anno. Importazione SVG completa, accesso Studio e diritti commerciali.',
    'donation_tier4_price' => '50.00€',
    'donation_tier4_amount' => '50.00',
    'donation_tier4_days' => '365',
    'donation_tier4_url' => '',

    // PayPal API Config
    'paypal_client_id' => '', // Public Key
    'paypal_secret' => '', // Secret Key (Server side only)
    'paypal_mode' => 'sandbox', // sandbox or live
];

if ($method === 'GET') {
    try {
        // Enforce DB existence
        $pdo->exec("CREATE TABLE IF NOT EXISTS settings (
            setting_key VARCHAR(50) PRIMARY KEY,
            setting_value TEXT
        )");

        // Fetch existing
        $stmt = $pdo->query("SELECT * FROM settings");
        $dbSettings = [];
        while ($row = $stmt->fetch()) {
            $dbSettings[$row['setting_key']] = $row['setting_value'];
        }

        // Merge defaults with DB
        $finalSettings = array_merge($defaults, $dbSettings);
        
        // Backfill missing keys
        foreach ($defaults as $k => $v) {
            if (!isset($dbSettings[$k])) {
                 $ins = $pdo->prepare("INSERT IGNORE INTO settings (setting_key, setting_value) VALUES (?, ?)");
                 $ins->execute([$k, $v]);
            }
        }

        // Check for public mode (Login Page)
        if (isset($_GET['mode']) && $_GET['mode'] === 'public') {
            $publicSettings = [];
            foreach ($finalSettings as $k => $v) {
                // Returns donation texts AND the PayPal Client ID for SDK Init
                if (strpos($k, 'donation_') === 0 || $k === 'paypal_client_id' || $k === 'paypal_mode') {
                    $publicSettings[$k] = $v;
                }
            }
            echo json_encode(['success' => true, 'settings' => $publicSettings]);
        } else {
            // Admin Mode (Return All)
            echo json_encode(['success' => true, 'settings' => $finalSettings]);
        }

    } catch (Exception $e) {
        $defaultsFiltered = $defaults;
        if (isset($_GET['mode']) && $_GET['mode'] === 'public') {
             $defaultsFiltered = array_filter($defaults, function($k) { return strpos($k, 'donation_') === 0 || $k === 'paypal_client_id'; }, ARRAY_FILTER_USE_KEY);
        }
        echo json_encode(['success' => true, 'settings' => $defaultsFiltered, 'warning' => 'DB_Config_Failed_Using_Defaults']);
    }
} elseif ($method === 'POST') {
    $input = json_decode(file_get_contents('php://input'), true);
    $action = $input['action'] ?? null;

    // Check for explicit action
    if ($action === 'test_donation') {
        ob_start(); // Start capturing output
        try {
            require_once 'mailer.php';
            
            $settingsToUse = null;
            if (isset($input['settings']) && is_array($input['settings'])) {
                $settingsToUse = $input['settings'];
            } else {
                $settingsToUse = getEmailSettings();
            }

            $adminEmail = $settingsToUse['admin_email'];
            $token = $settingsToUse['telegram_bot_token'] ?? 'N/A';
            $chatId = $settingsToUse['telegram_chat_id'] ?? 'N/A';
            
            // Mock Data for Test
            sendDonationEmail($adminEmail, "TestAdmin", "99.99", "ultra", date("Y-m-d", strtotime("+1 year")), $settingsToUse);
            
            $output = ob_get_clean(); // Get any warnings/echoes
            
            echo json_encode([
                'success' => true, 
                'debug' => [
                    'token_used' => substr($token, 0, 5) . '...',
                    'chat_id_used' => $chatId,
                    'admin_email_used' => $adminEmail,
                    'source' => isset($input['settings']) ? 'Frontend Input' : 'Database',
                    'server_output' => $output
                ]
            ]);
        } catch (Throwable $t) {
            $output = ob_get_clean();
            echo json_encode(['success' => false, 'error' => $t->getMessage(), 'output' => $output]);
        }
        exit;
    }
    if ($action === 'test_telegram') {
        $token = $input['token'] ?? '';
        $chatId = $input['chat_id'] ?? '';
        
        if (!$token || !$chatId) {
            echo json_encode(['success' => false, 'error' => 'Missing token or chat_id']);
            exit;
        }

        $msg = "<b>🧪 Keygen3d Connection Test</b>\n";
        $msg .= "This message confirms that your Telegram bot configuration is working correctly! 🚀";

        $result = sendTelegramNotificationLocal($token, $chatId, $msg);
        echo json_encode(['success' => $result]);
        exit;
    }
    
    // We expect an object of key->value pairs for normal save
    if (is_array($input)) {
        $stmt = $pdo->prepare("INSERT INTO settings (setting_key, setting_value) VALUES (?, ?) ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)");
        
        foreach ($input as $key => $value) {
            $stmt->execute([$key, $value]);
        }
        echo json_encode(['success' => true]);
    } else {
        echo json_encode(['success' => false, 'error' => 'Invalid input']);
    }
}

function sendTelegramNotificationLocal($token, $chatId, $message) {
    $url = "https://api.telegram.org/bot$token/sendMessage";
    $data = [
        'chat_id' => $chatId,
        'text' => $message,
        'parse_mode' => 'HTML'
    ];
    
    $options = [
        'http' => [
            'header'  => "Content-type: application/x-www-form-urlencoded\r\n",
            'method'  => 'POST',
            'content' => http_build_query($data),
            'ignore_errors' => true
        ]
    ];
    $context  = stream_context_create($options);
    $result = @file_get_contents($url, false, $context);
    return $result !== false;
}
?>
