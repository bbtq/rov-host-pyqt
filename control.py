import asyncio
import pygame


class Controller:
    def __init__(self):
        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        self.actions = []
        self.running = True  # Flag to control polling
        self._initialize_joystick()

    def _initialize_joystick(self):
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            print(f"Joystick connected: {self.joystick.get_name()}")
        else:
            print("No joystick connected.")

    async def poll_events(self):
        while self.running:
            pygame.event.pump()  # Make sure we only call this while running
            for event in pygame.event.get():
                if event.type == pygame.JOYBUTTONDOWN:
                    action = f"Button {event.button} pressed"
                    self.actions.append(action)
                elif event.type == pygame.JOYBUTTONUP:
                    action = f"Button {event.button} released"
                    self.actions.append(action)
            await asyncio.sleep(0.01)  # Avoid busy-waiting

    def get_actions(self):
        """Retrieve and clear the list of actions."""
        actions = self.actions[:]
        self.actions.clear()
        return actions

    def stop(self):
        """Stop polling and clean up resources."""
        self.running = False
        pygame.joystick.quit()  # Quit joystick system before pygame.quit()
        pygame.quit()  # Quit pygame after quitting joystick system
        print("Controller stopped and resources released.")
