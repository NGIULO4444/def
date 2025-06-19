#!/usr/bin/env python3
"""
VNC Server Cloud - Ottimizzato per deployment su servizi cloud
Supporta Railway, Fly.io, Heroku e altri provider
"""

import socket
import threading
import time
import logging
import json
import os
from vnc_protocol import VNCProtocol, MessageType

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VNCServerCloud:
    def __init__(self):
        # Porta da variabile ambiente (necessario per cloud)
        self.port = int(os.environ.get('PORT', 5901))
        self.host = '0.0.0.0'  # Bind su tutte le interfacce
        
        self.socket = None
        self.running = False
        
        # Gestione connessioni
        self.agents = {}
        self.controllers = {}
        self.agent_counter = 0
        self.lock = threading.Lock()
        
        # Statistiche
        self.stats = {
            'start_time': time.time(),
            'total_agents': 0,
            'total_controllers': 0
        }
    
    def start(self):
        """Avvia server cloud"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(100)
            self.running = True
            
            logging.info(f"🌩️ VNC Server Cloud avviato su porta {self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.socket.accept()
                    logging.info(f"🔗 Connessione da {address}")
                    
                    thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    thread.start()
                    
                except socket.error as e:
                    if self.running:
                        logging.error(f"Errore: {e}")
        
        except Exception as e:
            logging.error(f"❌ Errore avvio: {e}")
        finally:
            self.stop()
    
    def handle_client(self, client_socket, address):
        """Gestisce connessione client"""
        buffer = b''
        client_type = None
        session_id = None
        
        try:
            client_socket.settimeout(300)
            
            while self.running:
                data = client_socket.recv(8192)
                if not data:
                    break
                
                buffer += data
                
                while buffer:
                    msg_type, msg_data, buffer = VNCProtocol.unpack_message(buffer)
                    if msg_type is None:
                        break
                    
                    result = self.process_message(
                        client_socket, address, msg_type, msg_data,
                        client_type, session_id
                    )
                    
                    if result:
                        client_type, session_id = result
        
        except Exception as e:
            logging.error(f"❌ Errore client {address}: {e}")
        finally:
            self.cleanup_client(client_socket, client_type, session_id)
    
    def process_message(self, client_socket, address, msg_type, msg_data, client_type, session_id):
        """Processa messaggio"""
        
        if msg_type == MessageType.AGENT_CONNECT:
            return self.handle_agent_connect(client_socket, address)
        
        elif msg_type == MessageType.CONTROLLER_CONNECT:
            return self.handle_controller_connect(client_socket, address, msg_data)
        
        elif msg_type == MessageType.SCREEN_UPDATE:
            self.handle_screen_update(session_id, msg_data)
        
        elif msg_type == MessageType.MOUSE_MOVE or msg_type == MessageType.MOUSE_CLICK:
            self.handle_mouse_command(session_id, msg_type, msg_data)
        
        elif msg_type == MessageType.KEY_PRESS:
            self.handle_key_command(session_id, msg_data)
        
        return client_type, session_id
    
    def handle_agent_connect(self, client_socket, address):
        """Connessione agent"""
        with self.lock:
            self.agent_counter += 1
            session_id = f"agent_{self.agent_counter}"
            
            self.agents[session_id] = {
                'socket': client_socket,
                'address': address,
                'connected_time': time.time()
            }
            
            self.controllers[session_id] = []
            self.stats['total_agents'] += 1
        
        logging.info(f"🖥️ Agent {session_id} da {address}")
        
        response = VNCProtocol.pack_message(
            MessageType.CONNECTION_INFO,
            {'session_id': session_id, 'status': 'connected'}
        )
        client_socket.send(response)
        
        return 'agent', session_id
    
    def handle_controller_connect(self, client_socket, address, msg_data):
        """Connessione controller"""
        try:
            data = json.loads(msg_data.decode('utf-8'))
            session_id = data.get('session_id')
            
            if not session_id or session_id not in self.agents:
                available_agents = list(self.agents.keys())
                response = VNCProtocol.pack_message(
                    MessageType.CONNECTION_INFO,
                    {'available_agents': available_agents}
                )
                client_socket.send(response)
                return 'controller', None
            
            with self.lock:
                self.controllers[session_id].append({
                    'socket': client_socket,
                    'address': address,
                    'connected_time': time.time()
                })
                self.stats['total_controllers'] += 1
            
            logging.info(f"🎮 Controller su {session_id} da {address}")
            
            response = VNCProtocol.pack_message(
                MessageType.CONNECTION_INFO,
                {'session_id': session_id, 'status': 'connected'}
            )
            client_socket.send(response)
            
            return 'controller', session_id
            
        except Exception as e:
            logging.error(f"❌ Errore controller: {e}")
            return 'controller', None
    
    def handle_screen_update(self, session_id, screen_data):
        """Inoltra schermo"""
        if session_id not in self.controllers or not self.controllers[session_id]:
            return
        
        message = VNCProtocol.pack_message(MessageType.SCREEN_DATA, screen_data)
        
        with self.lock:
            controllers_to_remove = []
            for i, controller in enumerate(self.controllers[session_id]):
                try:
                    controller['socket'].send(message)
                except:
                    controllers_to_remove.append(i)
            
            for i in reversed(controllers_to_remove):
                del self.controllers[session_id][i]
    
    def handle_mouse_command(self, session_id, msg_type, msg_data):
        """Inoltra mouse"""
        if session_id in self.agents:
            try:
                message = VNCProtocol.pack_message(MessageType.COMMAND_MOUSE, msg_data)
                self.agents[session_id]['socket'].send(message)
            except:
                pass
    
    def handle_key_command(self, session_id, msg_data):
        """Inoltra tastiera"""
        if session_id in self.agents:
            try:
                message = VNCProtocol.pack_message(MessageType.COMMAND_KEY, msg_data)
                self.agents[session_id]['socket'].send(message)
            except:
                pass
    
    def cleanup_client(self, client_socket, client_type, session_id):
        """Pulizia disconnessione"""
        client_socket.close()
        
        if not session_id:
            return
        
        with self.lock:
            if client_type == 'agent' and session_id in self.agents:
                del self.agents[session_id]
                if session_id in self.controllers:
                    for controller in self.controllers[session_id]:
                        try:
                            controller['socket'].close()
                        except:
                            pass
                    del self.controllers[session_id]
                
                logging.info(f"🖥️ Agent {session_id} disconnesso")
            
            elif client_type == 'controller' and session_id in self.controllers:
                controllers = self.controllers[session_id]
                self.controllers[session_id] = [
                    c for c in controllers if c['socket'] != client_socket
                ]
                logging.info(f"🎮 Controller disconnesso da {session_id}")
    
    def stop(self):
        """Ferma server"""
        self.running = False
        if self.socket:
            self.socket.close()
        logging.info("🛑 Server fermato")

if __name__ == "__main__":
    server = VNCServerCloud()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n🛑 Arresto server...")
        server.stop() 