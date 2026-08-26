<?php
ini_set('display_errors', 1);
error_reporting(E_ALL);

echo "<h1>Debug Mailer</h1>";

echo "<h2>1. Checking Database & Settings</h2>";
require_once 'db.php';
require_once 'mailer.php';

try {
    $settings = getEmailSettings();
    echo "<pre>Settings Loaded:\n";
    // Hide passwords for security in output, show existence
    $safeSettings = $settings;
    if(isset($safeSettings['smtp_pass'])) $safeSettings['smtp_pass'] = '********';
    if(isset($safeSettings['telegram_bot_token'])) $safeSettings['telegram_bot_token'] = substr($safeSettings['telegram_bot_token'], 0, 5) . '...';
    print_r($safeSettings);
    echo "</pre>";
} catch (Exception $e) {
    echo "<p style='color:red'>Failed to load settings: " . $e->getMessage() . "</p>";
    exit;
}

echo "<h2>2. Testing Telegram</h2>";
if (!empty($settings['telegram_bot_token']) && !empty($settings['telegram_chat_id'])) {
    echo "Attempting to send Telegram message...<br>";
    $msg = "Debug Test " . date("H:i:s");
    $url = "https://api.telegram.org/bot" . $settings['telegram_bot_token'] . "/sendMessage";
    $data = [
        'chat_id' => $settings['telegram_chat_id'],
        'text' => $msg
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
    $result = file_get_contents($url, false, $context);
    echo "Raw Result: <pre>" . htmlspecialchars($result) . "</pre>";
} else {
    echo "Skipping Telegram: Token or Chat ID invalid.<br>";
}

echo "<h2>3. Testing SMTP</h2>";
if (!empty($settings['smtp_host'])) {
    $mailer = new SimpleSMTP($settings);
    $adminEmail = $settings['admin_email'] ?? '';
    if ($adminEmail) {
        echo "Sending test email to Admin ($adminEmail)...<br>";
        $sent = $mailer->send($adminEmail, "Debug Email", "This is a debug email.");
        if ($sent) {
            echo "<span style='color:green'>Email Sent Successfully!</span>";
        } else {
            echo "<span style='color:red'>Email Failed. Check error_log or enable detailed logging in mailer.</span>";
        }
    } else {
        echo "No admin email configured.";
    }
} else {
    echo "Skipping SMTP: Host invalid.";
}
?>
