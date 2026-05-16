import rumps
import cv2
from cvzone.FaceMeshModule import FaceMeshDetector

class ScreenDistanceApp(rumps.App):
    def __init__(self):
        super().__init__("Screen Distance", icon=None)
        self.title = "Starting..."
        self.paused = False
    
        self.show_distance = False

        self.d = 0
        self.threshold = 50

        self.close_count = 0
        self.far_count = 0
        
        self.cap = cv2.VideoCapture(0)
        self.detector = FaceMeshDetector(maxFaces=1)

        self.timer = rumps.MenuItem("Pause", callback=self.toggle_pause)
        self.menu = [self.timer]
        self.set = rumps.MenuItem("Set distance", callback=self.set_distance)
        self.menu = [self.set]
        self.show = rumps.MenuItem("Show distance", callback=self.toggle_show)
        self.menu = [self.show]
        self.timer = rumps.Timer(self.update_distance, 1)
        self.timer.start()

    def toggle_pause(self, sender):
        self.paused = not self.paused
        sender.title = "Resume" if self.paused else "Pause"
        if self.paused:
            self.title = "⏸"
            self.cap.release()  # Release camera
        else:
            self.cap = cv2.VideoCapture(0)  # Reinitialize camera
            self.timer.start()

    def set_distance(self, sender):
       self.threshold = self.d

    def toggle_show(self, sender):
       self.show_distance = not self.show_distance

    def update_distance(self, _):
        if self.paused:
            return

        success, img = self.cap.read()
        if not success or img is None or img.size == 0:
            print("Warning: Invalid frame, skipping...")
        img, faces = self.detector.findFaceMesh(img, draw=False)

        if faces:
            face = faces[0]
            pointLeft = face[145]
            pointRight = face[374]

            w, _ = self.detector.findDistance(pointLeft, pointRight)
            W = 6.9  # Approximate width of face in cm
            f = 1450  # Approximate focal length
            d = (W * f) / w  # Calculated distance in cm
            self.d = d

            if self.show_distance:
                if d < self.threshold:
                    self.title = f"🔴 {round(d)}"
                    self.close_count += 1
                else:
                    self.title = f"🟢 {round(d)}"
                    self.far_count += 1
            else:
                if d < self.threshold:
                    self.title = "🔴"
                    self.close_count += 1
                else:
                    self.title = "🟢"
                    self.far_count += 1

            
            print(f"{self.title} | {round(d,2)} | {self.close_count}:{self.far_count}")

        else:
            self.title = "🫥"

if __name__ == "__main__":
    app = ScreenDistanceApp()
    app.run()
