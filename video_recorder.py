# video_recorder.py
import cv2
import pygame
import datetime
import obd
import sys
from threading import Thread
import time
import numpy as np

class VideoCaptureThread(Thread):
    def __init__(self, src=0, width=1280, height=960):
        super(VideoCaptureThread, self).__init__()
        self.cap = cv2.VideoCapture(src)
        if not self.cap.isOpened():
            print("Error: Camera is not opened.")
            sys.exit(1)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.frame = None
        self.running = True

    def run(self):
        try:
            while self.running:
                ret, frame = self.cap.read()
                if ret:
                    self.frame = frame
        except Exception as e:
            print(f"Video capture thread error: {e}")

    def stop(self):
        self.running = False
        self.cap.release()

def start_recording(desired_width, desired_height, frame_rate):
    # 녹화 설정
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    current_datetime = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    video_filename = f"video_{current_datetime}.avi"
    out = cv2.VideoWriter(video_filename, fourcc, frame_rate, (desired_width, desired_height))
    
    # Pygame 초기화
    pygame.init()
    screen = pygame.display.set_mode((desired_width, desired_height))
    clock = pygame.time.Clock()
    
    # 화면 녹화 루프
    recording = True
    while recording:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                recording = False
        
        # 화면 캡처
        screenshot = pygame.surfarray.array3d(screen)
        screenshot = np.swapaxes(screenshot, 0, 1)
        
        # 동영상에 프레임 추가
        out.write(screenshot)
        
        # 화면 업데이트
        pygame.display.update()
        clock.tick(frame_rate)
    
    # 녹화 종료
    out.release()
    pygame.quit()

def calculate_fps(last_time, frame_count):
    current_time = time.time()
    if (current_time - last_time) > 1:
        fps = frame_count / (current_time - last_time)
        last_time = current_time
        frame_count = 0
        return fps, last_time, frame_count
    frame_count += 1
    return None, last_time, frame_count

def add_text_to_frame(frame, speed, rpm, throttle, load, frame_width, frame_height):
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame_pygame = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))

    current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    font_path = "/usr/share/fonts/truetype/nanum/NanumGothicExtraBold.ttf"
    font_size = 25
    font = pygame.font.Font(font_path, font_size)
    text_surface = font.render(current_datetime, True, (0, 255, 0))

    data_text = f"Speed: {speed} km/h  RPM: {rpm}  Throttle: {throttle}%  Load: {load}%"
    data_surface = font.render(data_text, True, (0, 255, 0))

    new_surface = pygame.Surface((frame_width, frame_height))
    new_surface.blit(frame_pygame, (0, 0))
    new_surface.blit(text_surface, (10, 10))
    new_surface.blit(data_surface, (10, frame_height - 40))

    new_frame = pygame.surfarray.array3d(new_surface)
    new_frame = new_frame.swapaxes(0, 1)
    new_frame = cv2.cvtColor(new_frame, cv2.COLOR_RGB2BGR)

    return new_frame
    
def video_recorder_main(connection=None, frame_rate=30, desired_width=1280, desired_height=960):
    
    # Pygame 디스플레이 설정을 실제 디스플레이 크기에 맞추어 전체 화면으로 설정
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    frame_width, frame_height = screen.get_size()  # 실제 디스플레이의 크기를 가져옴
    
    # Pygame 디스플레이 초기화
    try:
        screen_info = pygame.display.Info()
        frame_width = screen_info.current_w
        frame_height = int(frame_width / (float(desired_width) / float(desired_height)))
        screen = pygame.display.set_mode((desired_width, desired_height), pygame.FULLSCREEN)
    except Exception as e:
        print(f"Pygame display initialization error: {e}")
        sys.exit(1)

    video_thread = VideoCaptureThread(src=0, width=desired_width, height=desired_height)
    video_thread.start()

    recording = False
    out = None
    
    last_time = time.time()
    frame_count = 0
            
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                video_thread.stop()
                if out:
                    out.release()
                pygame.quit()
                sys.exit()
        
        # FPS 계산
        fps, last_time, frame_count = calculate_fps(last_time, frame_count)
        if fps:
            print(f"Current FPS: {fps}")
            
        if video_thread.frame is not None:
            frame = video_thread.frame.copy()

            speed, rpm, throttle, load = (0, 0, 0, 0)

            if connection:
                try:
                    speed = connection.query(obd.commands.SPEED).value.to("km/h")
                    rpm = connection.query(obd.commands.RPM).value
                    throttle = connection.query(obd.commands.THROTTLE_POS).value
                    load = connection.query(obd.commands.ENGINE_LOAD).value
                except Exception as e:
                    print(f"OBD-II error: {e}")

            frame_with_data = add_text_to_frame(frame, speed, rpm, throttle, load, frame_width, frame_height)

            keys = pygame.key.get_pressed()
            if keys[pygame.K_r]:
                recording = not recording
                if recording:
                    current_datetime = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    video_filename = f"video_{current_datetime}.avi"
                    out = cv2.VideoWriter(video_filename, cv2.VideoWriter_fourcc(*'XVID'), frame_rate, (desired_width, desired_height))
                    if not out.isOpened():
                        print("Error: Video Writer is not opened.")
                        recording = False
                    else:
                        print(f"Recording to {video_filename}")

            if recording:
                out.write(frame_with_data)

            frame_with_data = cv2.cvtColor(frame_with_data, cv2.COLOR_BGR2RGB)
            frame_with_data = pygame.surfarray.make_surface(frame_with_data.swapaxes(0, 1))
            screen.blit(frame_with_data, (0, 0))
            pygame.display.flip()
        
        # Sleep to give some time back to the CPU
        time.sleep(1.0 / frame_rate)
        
if __name__ == "__main__":
    video_recorder_main(connection=None, frame_rate=30, desired_width=800, desired_height=480)
