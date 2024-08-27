from flask import Flask, render_template, Response, jsonify
import cv2
import mediapipe as mp
import numpy as np
import requests

app = Flask(__name__)

esp32_cam_url = "http://192.168.41.165:80"  # Adjust to your ESP32-CAM stream URL
esp32_server_url = "http://192.168.41.17"  # Adjust to your ESP32 server URL

# Initialize MediaPipe Face Detection
mp_face_detection = mp.solutions.face_detection
face_detection = mp_face_detection.FaceDetection(min_detection_confidence=0.2)

# VGA Resolution
frame_width = 640
frame_height = 480
line1_y = int(frame_height / 3)
line2_y = int(2 * frame_height / 3)

# Initialize tracking variables
face_tracker = {}
face_id_counter = 0
total_faces_entered = 0
face_lines = {}

def assign_face_id(face_box, tracked_faces):
    for face_id, (box, _) in tracked_faces.items():
        if iou(face_box, box) > 0.5:
            return face_id
    return None

def iou(box1, box2):
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    xA = max(x1, x2)
    yA = max(y1, y2)
    xB = min(x1 + w1, x2 + w2)
    yB = min(y1 + h1, y2 + h2)
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = w1 * h1
    boxBArea = w2 * h2
    return interArea / float(boxAArea + boxBArea - interArea)

def send_count_to_esp32(count):
    try:
        response = requests.post(f"{esp32_server_url}/update_count", json={"total_faces": count})
        if response.status_code == 200:
            print(f"Successfully sent count to ESP32: {count}")
        else:
            print(f"Failed to send count to ESP32. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending count to ESP32: {e}")

def generate_frames():
    global face_tracker, face_id_counter, total_faces_entered, face_lines
    stream = requests.get(esp32_cam_url, stream=True)
    if stream.status_code != 200:
        print("Failed to connect to ESP32-CAM stream.")
        return

    bytes_stream = bytes()
    previous_centroids = []

    for chunk in stream.iter_content(chunk_size=1024):
        bytes_stream += chunk
        a = bytes_stream.find(b'\xff\xd8')
        b = bytes_stream.find(b'\xff\xd9')
        if a != -1 and b != -1:
            jpg = bytes_stream[a:b+2]
            bytes_stream = bytes_stream[b+2:]
            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_detection.process(rgb_frame)
                detected_faces = []

                if results.detections:
                    for detection in results.detections:
                        bboxC = detection.location_data.relative_bounding_box
                        ih, iw, _ = frame.shape
                        x, y, w, h = int(bboxC.xmin * iw), int(bboxC.ymin * ih), int(bboxC.width * iw), int(bboxC.height * ih)
                        detected_faces.append([x, y, w, h])
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        cv2.putText(frame, "Face", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                new_face_tracker = {}
                for face_box in detected_faces:
                    face_id = assign_face_id(face_box, face_tracker)
                    if face_id is None:
                        face_id = face_id_counter
                        face_id_counter += 1
                    new_face_tracker[face_id] = (face_box, np.array(face_box))

                face_tracker = new_face_tracker

                cv2.line(frame, (0, line1_y), (frame.shape[1], line1_y), (0, 255, 255), 2)
                cv2.line(frame, (0, line2_y), (frame.shape[1], line2_y), (0, 255, 255), 2)

                for face_id, (box, _) in face_tracker.items():
                    x, y, w, h = box
                    if y + h > line1_y and y < line1_y:
                        if face_id not in face_lines:
                            face_lines[face_id] = 'entering_line1'
                    elif y + h > line2_y and y < line2_y:
                        if face_id in face_lines and face_lines[face_id] == 'entering_line1':
                            total_faces_entered += 1
                            del face_lines[face_id]

                face_count = len(face_tracker)
                cv2.putText(frame, f"Face Count: {face_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.putText(frame, f"Total Faces Entered: {total_faces_entered}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

                # Send count to ESP32 and check if we need to trigger the buzzer and LED
                send_count_to_esp32(total_faces_entered)
                if total_faces_entered > 50:
                    requests.post(f"{esp32_server_url}/on")

                ret, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/counts')
def counts():
    global total_faces_entered, face_tracker
    face_count = len(face_tracker)
    return jsonify(face_count=face_count, total_faces_entered=total_faces_entered)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
