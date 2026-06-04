import { useEffect } from 'react'
import { io } from 'socket.io-client'
import { useRoomStore } from '../store/useRoomStore'

export const useSocket = () => {
  const { isAuthenticated, setSocket, setHostsCount, socket } = useRoomStore()

  useEffect(() => {
    if (!isAuthenticated) {
      if (socket) {
        socket.disconnect()
        setSocket(null)
      }
      return
    }

    // Connect to signaling server (proxied through Vite)
    const newSocket = io({
      autoConnect: true,
      withCredentials: true,
    })

    newSocket.on('connect', () => {
      console.log('Connected to signaling server with ID:', newSocket.id)
    })

    newSocket.on('server_status', (data: { hosts_count: number }) => {
      setHostsCount(data.hosts_count)
    })

    newSocket.on('connect_error', (err) => {
      console.error('Socket connection error:', err)
    })

    setSocket(newSocket)

    return () => {
      newSocket.disconnect()
      setSocket(null)
    }
  }, [isAuthenticated, setSocket, setHostsCount])
}
