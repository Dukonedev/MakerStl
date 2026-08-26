<?php
// Standalone Fonts Handler - BASED ON TEMPLATES.PHP
// capturing all stray output/errors to prevent Invalid JSON
ob_start(); 

header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST, OPTIONS, DELETE");
header("Access-Control-Allow-Headers: Content-Type");
header("Content-Type: application/json");

if ($_SERVER['REQUEST_METHOD'] == 'OPTIONS') {
    ob_end_clean(); // Clean anything before exiting
    http_response_code(200);
    exit;
}

// Disable native styling of errors just in case
ini_set('html_errors', 0); 
ini_set('display_errors', 0);
ini_set('log_errors', 1);
error_reporting(E_ALL);

function send_json_response($data) {
    // Clear any previous output (warnings, notices, HTML)
    if (ob_get_length()) ob_clean(); 
    echo json_encode($data);
    exit;
}

// Critical Error Handler
register_shutdown_function(function() {
    $error = error_get_last();
    if ($error && ($error['type'] === E_ERROR || $error['type'] === E_PARSE || $error['type'] === E_CORE_ERROR || $error['type'] === E_COMPILE_ERROR)) {
        if (ob_get_length()) ob_clean();
        header("Access-Control-Allow-Origin: *"); 
        header("Content-Type: application/json");
        echo json_encode(['success' => false, 'error' => "FATAL PHP ERROR: " . $error['message'] . " (Line " . $error['line'] . ")"]);
        exit;
    }
});

try {
    // Parse Input (JSON or POST)
    $rawInput = file_get_contents('php://input');
    $jsonData = json_decode($rawInput, true);

    // Determine Action
    $action = '';
    if (isset($_POST['action'])) {
        $action = $_POST['action'];
    } elseif (isset($_GET['action'])) {
        $action = $_GET['action'];
    } elseif ($jsonData && isset($jsonData['action'])) {
        $action = $jsonData['action'];
    }

    // Check POST Max Size Limit
    // Only throw if it looks like a failed upload (empty POST/FILES but content length > 0)
    // AND it's NOT a valid JSON request
    if ($_SERVER['REQUEST_METHOD'] == 'POST' && empty($_POST) && empty($_FILES) && $_SERVER['CONTENT_LENGTH'] > 0 && !$jsonData) {
        throw new Exception("File exceeds server limit (post_max_size).");
    }

    $fontsDir = __DIR__ . '/../fonts/';

    // Attempt to create dir
    if (!file_exists($fontsDir)) {
        if (!@mkdir($fontsDir, 0755, true)) {
             // Continue, we will check writable later
        }
    }

    // --- ACTION: LIST ---
    if ($action === 'list') {
        if (!is_dir($fontsDir)) send_json_response(['success' => true, 'fonts' => []]);
        
        $mode = $_GET['mode'] ?? 'public'; // 'public' or 'admin'
        
        $files = scandir($fontsDir);
        $fonts = [];
        foreach ($files as $file) {
            if ($file === '.' || $file === '..') continue;
            
            $ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
            if ($ext !== 'ttf' && $ext !== 'otf') continue;
            
            $isHidden = (strpos($file, '_hidden_') === 0);
            
            if ($mode === 'admin') {
                // Admin sees everything
                $fonts[] = $file; 
            } else {
                // Public sees only visible files
                if (!$isHidden) {
                    $fonts[] = $file;
                }
            }
        }
        send_json_response(['success' => true, 'fonts' => $fonts]);
    }

    // --- ACTION: RENAME ---
    if ($action === 'rename') {
        $input = json_decode(file_get_contents('php://input'), true);
        $oldName = $input['old_name'] ?? $_POST['old_name'] ?? '';
        $newName = $input['new_name'] ?? $_POST['new_name'] ?? '';
        
        if (!$oldName || !$newName) send_json_response(['success' => false, 'error' => 'Missing names']);
        
        // Security & Sanitization
        $oldName = basename($oldName);
        $cleanNewName = preg_replace('/[^a-zA-Z0-9 _-]/', '', $newName); // Keep safe chars
        if (empty($cleanNewName)) send_json_response(['success' => false, 'error' => 'Invalid new name']);
        
        $currentExt = strtolower(pathinfo($oldName, PATHINFO_EXTENSION));
        
        if (!str_ends_with(strtolower($cleanNewName), '.' . $currentExt)) {
             $cleanNewName .= '.' . $currentExt;
        }
        
        $oldPath = $fontsDir . $oldName;
        $newPath = $fontsDir . $cleanNewName;
        
        if (!file_exists($oldPath)) send_json_response(['success' => false, 'error' => 'File not found']);
        if (file_exists($newPath)) send_json_response(['success' => false, 'error' => 'Name already taken']);
        
        if (rename($oldPath, $newPath)) {
            send_json_response(['success' => true, 'new_name' => $cleanNewName]);
        } else {
            send_json_response(['success' => false, 'error' => 'Rename failed']);
        }
    }

    // --- ACTION: TOGGLE VISIBILITY ---
    if ($action === 'toggle_visibility') {
        $input = json_decode(file_get_contents('php://input'), true);
        $filename = $input['filename'] ?? $_POST['filename'] ?? '';
        
        if (!$filename) send_json_response(['success' => false, 'error' => 'Filename required']);
        $filename = basename($filename);
        $oldPath = $fontsDir . $filename;
        
        if (!file_exists($oldPath)) send_json_response(['success' => false, 'error' => 'File not found']);
        
        $isHidden = (strpos($filename, '_hidden_') === 0);
        
        if ($isHidden) {
            // UNHIDE: Remove _hidden_ prefix
            $newFilename = substr($filename, 8); // strlen('_hidden_') = 8
        } else {
            // HIDE: Add _hidden_ prefix
            $newFilename = '_hidden_' . $filename;
        }
        
        $newPath = $fontsDir . $newFilename;
        if (rename($oldPath, $newPath)) {
            send_json_response(['success' => true, 'new_name' => $newFilename, 'visible' => $isHidden]); // visible is now true if was hidden
        } else {
             send_json_response(['success' => false, 'error' => 'Toggle failed']);
        }
    }

    // --- ACTION: GET (Download file) ---
    if ($action === 'get') {
        $filename = $_GET['filename'] ?? '';
        $filename = basename($filename); // Security
        $targetPath = $fontsDir . $filename;
        
        if (file_exists($targetPath)) {
             // Clear existing JSON header and any buffered output
            if (ob_get_length()) ob_clean();
            
            $ext = strtolower(pathinfo($filename, PATHINFO_EXTENSION));
            $contentType = 'application/octet-stream';
            if ($ext === 'ttf') $contentType = 'font/ttf';
            if ($ext === 'otf') $contentType = 'font/otf';
            
            header("Content-Type: " . $contentType);
            // Disable caching to ensure fresh load
            header("Cache-Control: no-cache, no-store, must-revalidate");
            echo file_get_contents($targetPath);
            exit;
        } else {
             http_response_code(404);
             echo "File not found";
             exit;
        }
    }

    // --- ACTION: UPLOAD ---
    if ($action === 'upload') {
        if (!isset($_FILES['file'])) send_json_response(['success' => false, 'error' => 'No file received']);

        $file = $_FILES['file'];
        if ($file['error'] !== UPLOAD_ERR_OK) {
             throw new Exception("Upload Error Code: " . $file['error']);
        }

        $inputExt = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));

        // HANDLE ZIP UPLOAD
        if ($inputExt === 'zip') {
            $zip = new ZipArchive;
            if ($zip->open($file['tmp_name']) === TRUE) {
                $uploadedFiles = [];
                $errors = [];
                
                for ($i = 0; $i < $zip->numFiles; $i++) {
                    $filename = $zip->getNameIndex($i);
                    $fileinfo = pathinfo($filename);
                    $ext = strtolower($fileinfo['extension'] ?? '');
                    
                    // Skip directories and non-font files
                    if (substr($filename, -1) == '/') continue;
                    if ($ext !== 'ttf' && $ext !== 'otf') continue;
                    
                    // Sanitize filename (flatten directory structure)
                    $cleanName = preg_replace('/[^a-zA-Z0-9 _-]/', '', $fileinfo['filename']);
                    if (empty($cleanName)) $cleanName = "font_" . time() . "_" . $i;
                    
                    $targetFilename = $cleanName . '.' . $ext;
                    $targetPath = $fontsDir . $targetFilename;
                    
                    // Copy file from zip
                    $stream = $zip->getStream($filename);
                    if ($stream) {
                        $fp = fopen($targetPath, 'w');
                        if ($fp) {
                            while (!feof($stream)) {
                                fwrite($fp, fread($stream, 8192));
                            }
                            fclose($fp);
                            fclose($stream);
                            $uploadedFiles[] = $targetFilename;
                        } else {
                            $errors[] = "Could not write $targetFilename";
                        }
                    } else {
                        $errors[] = "Could not read $filename";
                    }
                }
                $zip->close();
                
                if (empty($uploadedFiles)) {
                    send_json_response(['success' => false, 'error' => 'No valid fonts found in ZIP']);
                }
                
                send_json_response(['success' => true, 'files' => $uploadedFiles, 'errors' => $errors]);
            } else {
                throw new Exception("Failed to open ZIP file");
            }
        }

        // HANDLE SINGLE FILE UPLOAD
        $originalName = pathinfo($file['name'], PATHINFO_FILENAME);
        $customName = $_POST['name'] ?? $originalName;
        $customName = trim($customName);
        if (empty($customName)) $customName = $originalName;
        
        $safeName = preg_replace('/[^a-zA-Z0-9 _-]/', '', $customName);
        if (empty($safeName)) $safeName = "font_" . time();
        
        if ($inputExt !== 'ttf' && $inputExt !== 'otf') send_json_response(['success' => false, 'error' => 'Only TTF, OTF, or ZIP files allowed']);
        
        $filename = $safeName . '.' . $inputExt;
        $targetPath = $fontsDir . $filename;

        // Check if writable
        if (!is_writable($fontsDir) && !is_writable(dirname($fontsDir))) {
             throw new Exception("Server folder not writable. Permissions needed for: " . $fontsDir);
        }

        if (move_uploaded_file($file['tmp_name'], $targetPath)) {
            send_json_response(['success' => true, 'file' => $filename]);
        } else {
            $last = error_get_last();
            throw new Exception("Move failed. " . ($last['message'] ?? ''));
        }
    }

    // --- ACTION: DELETE ---
    if ($action === 'delete') {
        $input = json_decode(file_get_contents('php://input'), true);
        $filename = $input['filename'] ?? $_POST['filename'] ?? '';
        if (!$filename) send_json_response(['success' => false, 'error' => 'Filename required']);
        $targetPath = $fontsDir . basename($filename);
        if (file_exists($targetPath)) {
            unlink($targetPath) ? send_json_response(['success' => true]) : send_json_response(['success' => false, 'error' => 'Delete failed']);
        }
        send_json_response(['success' => false, 'error' => 'File not found']);
    }

    send_json_response(['success' => false, 'error' => 'Invalid action']);

} catch (Throwable $t) {
    send_json_response(['success' => false, 'error' => $t->getMessage()]);
}
?>
