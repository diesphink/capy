import io

import libsonic
import pygame


class AudioBackend:
    MUSIC_END = pygame.USEREVENT + 1

    def __init__(self, conn: libsonic.Connection, fn_end_music) -> None:

        self.conn = conn
        self.fn_end_music = fn_end_music

        pygame.init()
        pygame.mixer.init()

        pygame.mixer.music.set_endevent(AudioBackend.MUSIC_END)

    def play(self, song):
        # music = self.conn.download(song["id"])
        # print(music)
        # pygame.mixer.music.load(music, "music")
        # audio_buffer = io.BytesIO(self.conn.stream(song["id"]).read())
        audio_buffer = io.BytesIO(self.conn.download(song["id"]).read())
        pygame.mixer.music.load(audio_buffer)

        pygame.mixer.music.play()

    def destroy(self):
        print("Stopping audio backend")
        pygame.mixer.music.stop()

    def loop(self):
        import time

        for event in pygame.event.get():
            if event.type == AudioBackend.MUSIC_END:
                print("Music ended!")
                self.fn_end_music()
            time.sleep(1)
            print(event)

    def seek(self, time: int) -> None:
        pygame.mixer.music.set_pos(pygame.mixer.music.get_pos() + time)
