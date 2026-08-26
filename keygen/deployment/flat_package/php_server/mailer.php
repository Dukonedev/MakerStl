<?php
// mailer.php
// Handles Email (SMTP) and Telegram Notifications

// Optional config require
if (file_exists('mail_config.php')) {
    require_once 'mail_config.php';
}

error_reporting(E_ALL & ~E_NOTICE & ~E_WARNING);
ini_set('display_errors', 0);

if (!class_exists('SimpleSMTP')) {
    class SimpleSMTP {
        private $sock;
        private $settings;
        private $host;
        private $port;
        private $user;
        private $pass;
    
        public function __construct($settings) {
            $this->settings = $settings;
            $this->host = $settings['smtp_host'] ?? '';
            $this->port = $settings['smtp_port'] ?? 587;
            $this->user = $settings['smtp_user'] ?? '';
            $this->pass = $settings['smtp_pass'] ?? '';
        }
    
        public function send($to, $subject, $body) {
            if (!$this->host || !$this->user) {
                // Fallback to PHP mail() if SMTP not configured
                // But generally we want SMTP.
                return false;
            }
    
            try {
                if (!$this->connect()) return false;
                
                $this->cmd("EHLO " . $this->host);
                if (function_exists('stream_socket_enable_crypto')) {
                     $this->cmd("STARTTLS");
                     stream_socket_enable_crypto($this->sock, true, STREAM_CRYPTO_METHOD_TLS_CLIENT);
                     $this->cmd("EHLO " . $this->host);
                }
    
                $this->cmd("AUTH LOGIN");
                $this->cmd(base64_encode($this->user));
                $this->cmd(base64_encode($this->pass));
    
                $fromEmail = $this->settings['smtp_from_email'] ?? 'noreply@example.com';
                $fromName = $this->settings['smtp_from_name'] ?? 'Keygen3d';
    
                $this->cmd("MAIL FROM: <$fromEmail>");
                $this->cmd("RCPT TO: <$to>");
                $this->cmd("DATA");
    
                $headers = "MIME-Version: 1.0\r\n";
                $headers .= "Content-Type: text/html; charset=UTF-8\r\n";
                $headers .= "From: $fromName <$fromEmail>\r\n";
                $headers .= "To: $to\r\n";
                $headers .= "Subject: $subject\r\n";
    
                fwrite($this->sock, "$headers\r\n$body\r\n.\r\n");
                $response = $this->read();
                
                $this->cmd("QUIT");
                fclose($this->sock);
    
                return substr($response, 0, 3) == '250';
            } catch (Exception $e) {
                error_log("SMTP Error: " . $e->getMessage());
                return false;
            }
        }
    
        private function connect() {
            $socket_options = [
                'ssl' => [
                    'verify_peer' => false,
                    'verify_peer_name' => false,
                ]
            ];
            // 10s timeout
            $this->sock = stream_socket_client("tcp://{$this->host}:{$this->port}", $errno, $errstr, 10, STREAM_CLIENT_CONNECT, stream_context_create($socket_options));
            if (!$this->sock) {
                error_log("SMTP Connect Failed: $errstr ($errno)");
                return false;
            }
            $this->read(); 
            return true;
        }
    
        private function cmd($command) {
            if ($this->sock) {
                fwrite($this->sock, $command . "\r\n");
                return $this->read();
            }
            return "";
        }
    
        private function read() {
            if (!$this->sock) return "";
            $response = "";
            $start = time();
            while ($str = fgets($this->sock, 515)) {
                $response .= $str;
                if (substr($str, 3, 1) == " ") break;
                if (time() - $start > 5) break; // Safety break
            }
            return $response;
        }
    }
} // End class_exists check

if (!function_exists('getEmailSettings')) {
    function getEmailSettings() {
        global $pdo; 
        if (!isset($pdo) || !$pdo) {
             if (file_exists('db.php')) require_once 'db.php';
        }
        
        if (isset($pdo) && $pdo) {
            $stmt = $pdo->query("SELECT * FROM settings");
            $settings = [];
            while ($row = $stmt->fetch()) {
                $settings[$row['setting_key']] = $row['setting_value'];
            }
            return $settings;
        }
        return [];
    }
}

if (!function_exists('sendRegistrationEmail')) {
    function sendRegistrationEmail($recipientEmail, $username, $plainPassword) {
        $settings = getEmailSettings();
        $mailer = new SimpleSMTP($settings);
    
        // 1. Send to USER
        if (strpos($recipientEmail, '@') !== false) {
            $subject = $settings['email_welcome_subject'] ?? 'Welcome!';
            $body = $settings['email_welcome_body'] ?? 'Welcome {USERNAME}';
            
            $body = str_replace('{USERNAME}', $username, $body);
            $body = str_replace('{PASSWORD}', $plainPassword, $body);
            
            // Append Rich Donation Info
            $donationHtml = '
            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 40px; border-top: 1px solid #333; padding-top: 40px;">
                <tr>
                    <td align="center">
                        <h3 style="color: #a3e635; font-family: monospace; text-transform: uppercase; font-size: 24px; margin: 0 0 10px 0; letter-spacing: -1px;">Support The Project</h3>
                        <p style="color: #71717a; font-family: monospace; text-transform: uppercase; font-size: 12px; margin: 0 0 30px 0; letter-spacing: 2px;">Unlock advanced features & servers</p>
                    </td>
                </tr>
                <tr>
                    <td align="center">
                        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px;">';
            
            // Loop for Tiers (2x2 Grid simulation for Email)
            // Since email grids are hard, we will stack them vertically on mobile, but try to do 2 per row if width allows.
            // For max compatibility, a vertical stack of "Cards" is best.
            
            for ($i=1; $i<=4; $i++) {
                $title = $settings["donation_tier{$i}_title"] ?? "Tier $i";
                $desc = $settings["donation_tier{$i}_desc"] ?? "Support us!";
                $price = $settings["donation_tier{$i}_price"] ?? "";
                $link = $settings["donation_tier{$i}_url"] ?? "";
                
                $discountLabel = $settings["donation_tier{$i}_discount_label"] ?? "";
                $discountAmount = $settings["donation_tier{$i}_discount_amount"] ?? "";
                $hasDiscount = $discountAmount && floatval($discountAmount) > 0;
                
                // Colors based on tier
                $borderColor = '#27272a'; // Zinc
                $textColor = '#a1a1aa';
                $bgColor = '#18181b'; // Dark Zinc
                
                if ($i === 2) { // Standard - Blue
                    $borderColor = 'rgba(59, 130, 246, 0.3)';
                    $textColor = '#60a5fa';
                    $bgColor = 'rgba(59, 130, 246, 0.05)';
                } elseif ($i === 3) { // Pro - Emerald
                    $borderColor = 'rgba(52, 211, 153, 0.3)';
                    $textColor = '#34d399';
                    $bgColor = 'rgba(52, 211, 153, 0.05)';
                } elseif ($i === 4) { // Ultra - Purple
                    $borderColor = 'rgba(192, 132, 252, 0.3)';
                    $textColor = '#c084fc';
                    $bgColor = 'rgba(192, 132, 252, 0.05)';
                }
                
                $priceHtml = '';
                if ($hasDiscount) {
                     $priceHtml = '<span style="color: #71717a; text-decoration: line-through; font-size: 14px; margin-right: 10px;">'.$price.'</span><span style="color: #a3e635; font-size: 24px; font-weight: 900;">'.$discountLabel.'</span>';
                } else {
                     $priceHtml = '<span style="color: #fff; font-size: 24px; font-weight: 900;">'.$price.'</span>';
                }

                if ($price && $link) {
                    $donationHtml .= '
                    <tr>
                        <td style="padding-bottom: 20px;">
                            <table width="100%" cellpadding="20" cellspacing="0" border="0" style="background-color: '.$bgColor.'; border: 1px solid '.$borderColor.'; border-radius: 16px;">
                                <tr>
                                    <td style="font-family: Arial, sans-serif;">
                                        '. ($hasDiscount ? '<div style="float: right; background-color: #a3e635; color: #000; font-size: 10px; font-weight: 900; text-transform: uppercase; padding: 4px 8px; border-radius: 0 0 0 8px;">OFFER</div>' : '') .'
                                        <h3 style="color: '.$textColor.'; font-size: 18px; text-transform: uppercase; margin: 0 0 10px 0; font-weight: 700;">'.$title.'</h3>
                                        <div style="margin-bottom: 15px;">
                                            '.$priceHtml.'
                                        </div>
                                        <p style="color: #a1a1aa; font-size: 13px; margin: 0 0 20px 0; line-height: 1.5;">'.$desc.'</p>
                                        <table width="100%" cellspacing="0" cellpadding="0">
                                            <tr>
                                                <td align="center" style="background-color: #27272a; border-radius: 8px;">
                                                    <a href="'.$link.'" target="_blank" style="display: block; padding: 12px; color: #fff; text-decoration: none; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; font-family: monospace;">
                                                        Obtain License
                                                    </a>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>';
                }
            }
            $donationHtml .= '</table></td></tr></table>';
            
            $body .= $donationHtml;
    
            $mailer->send($recipientEmail, $subject, $body);
        }
    
        // 2. Send to ADMIN (Email)
        $adminEmail = $settings['admin_email'] ?? '';
        if ($adminEmail) {
            $subjectAdmin = "[New User] $username Registered";
            $bodyAdmin = "<html><body><h3>New User Registration</h3><p>Username: $username</p><p>Email: $recipientEmail</p></body></html>";
            $mailer->send($adminEmail, $subjectAdmin, $bodyAdmin);
        }
        
        // 3. Send to ADMIN (Telegram)
        $botToken = $settings['telegram_bot_token'] ?? '';
        $chatId = $settings['telegram_chat_id'] ?? '';
        
        if ($botToken && $chatId) {
            $msg = "<b>New User Registered</b>\nUser: $username";
            sendTelegramNotification($botToken, $chatId, $msg);
        }
        return true;
    }
}

// Telegram Function (cURL)
if (!function_exists('sendTelegramNotification')) {
    function sendTelegramNotification($token, $chatId, $message) {
        if (!$token || !$chatId) return;
    
        $url = "https://api.telegram.org/bot$token/sendMessage";
        $data = [
            'chat_id' => $chatId,
            'text' => $message,
            'parse_mode' => 'HTML'
        ];
        
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_POST, 1);
        curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($data));
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_TIMEOUT, 5); // 5s timeout
        
        $response = curl_exec($ch);
        curl_close($ch);
        // Error logging handled by caller or ignored to prevent crashes
    }
}

if (!function_exists('sendPasswordResetEmail')) {
    function sendPasswordResetEmail($recipientEmail, $newPassword) {
        if (strpos($recipientEmail, '@') === false) return false;
    
        $settings = getEmailSettings();
        $mailer = new SimpleSMTP($settings);
    
        $subject = $settings['email_reset_subject'] ?? 'Password Reset';
        $body = $settings['email_reset_body'] ?? 'New Password: {PASSWORD}';
        
        $body = str_replace('{PASSWORD}', $newPassword, $body);
    
        return $mailer->send($recipientEmail, $subject, $body);
    }
}

if (!function_exists('sendDonationEmail')) {
    function sendDonationEmail($userEmail, $username, $amount, $role, $expiryDate, $settingsOverride = null) {
        if ($settingsOverride) {
            $settings = $settingsOverride;
        } else {
            $settings = getEmailSettings();
        }
        $mailer = new SimpleSMTP($settings);
        
        // 1. Send to USER
        if ($userEmail && strpos($userEmail, '@') !== false) {
            $subject = $settings['email_donation_subject'] ?? 'Thank you for your donation!';
            $body = $settings['email_donation_body'] ?? 'Thanks for {AMOUNT} EUR. You are now {ROLE}.';
            
            $body = str_replace('{USERNAME}', $username, $body);
            $body = str_replace('{AMOUNT}', $amount, $body);
            $body = str_replace('{ROLE}', strtoupper($role), $body);
            $body = str_replace('{EXPIRY}', $expiryDate, $body);
            
            $mailer->send($userEmail, $subject, $body);
        }
    
        // 2. Send to ADMIN (Email)
        $adminEmail = $settings['admin_email'] ?? '';
        if ($adminEmail) {
            $subjectAdmin = $settings['email_admin_donation_subject'] ?? '[ALERT] New Donation';
            $bodyAdmin = $settings['email_admin_donation_body'] ?? '{USERNAME} donated {AMOUNT} EUR.';
            
            $bodyAdmin = str_replace('{USERNAME}', $username, $bodyAdmin);
            $bodyAdmin = str_replace('{EMAIL}', $userEmail, $bodyAdmin);
            $bodyAdmin = str_replace('{AMOUNT}', $amount, $bodyAdmin);
            $bodyAdmin = str_replace('{ROLE}', strtoupper($role), $bodyAdmin);
            
            $mailer->send($adminEmail, $subjectAdmin, $bodyAdmin);
        }
        
        // 3. Send to ADMIN (Telegram)
        $botToken = $settings['telegram_bot_token'] ?? '';
        $chatId = $settings['telegram_chat_id'] ?? '';
        
        if ($botToken && $chatId) {
            $msg = "<b>💰 New Donation Received</b>\n";
            $msg .= "👤 User: <code>$username</code>\n";
            $msg .= "📧 Email: <code>$userEmail</code>\n";
            $msg .= "💵 Amount: <b>€$amount</b>\n";
            $msg .= "🎖 Role: <b>$role</b>\n";
            $msg .= "⏳ Expiry: " . $expiryDate;
            
            sendTelegramNotification($botToken, $chatId, $msg);
        }
        
        return true;
    }
}
?>
