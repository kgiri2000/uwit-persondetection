import { useEffect, useRef } from 'react'
import { useRoomStore } from '../store/useRoomStore'

const rtcConfig: RTCConfiguration = {
  iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
}

export const useWebRTC = () => {
  const {
    socket,
    role,
    localStream,
    addRemoteStream,
    removeRemoteStream,
  } = useRoomStore()

  const pcs = useRef<{ [id: string]: RTCPeerConnection }>({})

  useEffect(() => {
    if (!socket) return
    if (role !== 'observer' && !localStream) return

    const createPeerConnection = (peerId: string, peerRole: 'host' | 'guest' | 'observer', peerName: string) => {
      if (pcs.current[peerId]) return pcs.current[peerId]

      const pc = new RTCPeerConnection(rtcConfig)

      // Add local stream tracks to the connection if available
      if (localStream) {
        localStream.getTracks().forEach((track) => {
          pc.addTrack(track, localStream)
        })
      }

      // Send local ICE candidates to remote peer
      pc.onicecandidate = (event) => {
        if (event.candidate) {
          socket.emit('signal', { target: peerId, candidate: event.candidate })
        }
      }

      // Capture incoming tracks
      pc.ontrack = (event) => {
        const remoteStream = event.streams[0]
        if (remoteStream) {
          addRemoteStream(peerId, remoteStream, peerRole, peerName)
        }
      }

      pc.onconnectionstatechange = () => {
        if (
          pc.connectionState === 'disconnected' ||
          pc.connectionState === 'failed' ||
          pc.connectionState === 'closed'
        ) {
          closePeer(peerId)
        }
      }

      pcs.current[peerId] = pc
      return pc
    }

    const closePeer = (peerId: string) => {
      const pc = pcs.current[peerId]
      if (pc) {
        pc.close()
        delete pcs.current[peerId]
      }
      removeRemoteStream(peerId)
    }

    // Handlers
    const handlePeerJoined = async (data: { id: string; role: 'host' | 'guest' | 'observer'; name: string }) => {
      const peerId = data.id
      const pc = createPeerConnection(peerId, data.role, data.name)
      if (!pc) return

      try {
        const offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        socket.emit('signal', { target: peerId, sdp: pc.localDescription })
      } catch (e) {
        console.error('Error creating WebRTC offer:', e)
      }
    }

    const handleSignal = async (data: {
      sender: string
      role: 'host' | 'guest' | 'observer'
      name: string
      sdp?: RTCSessionDescriptionInit
      candidate?: RTCIceCandidateInit
    }) => {
      const senderId = data.sender
      let pc = pcs.current[senderId]

      if (!pc) {
        pc = createPeerConnection(senderId, data.role, data.name)
      }

      if (!pc) return

      try {
        if (data.sdp) {
          await pc.setRemoteDescription(new RTCSessionDescription(data.sdp))
          if (data.sdp.type === 'offer') {
            const answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            socket.emit('signal', { target: senderId, sdp: pc.localDescription })
          }
        } else if (data.candidate) {
          await pc.addIceCandidate(new RTCIceCandidate(data.candidate))
        }
      } catch (e) {
        console.error('Signal processing error:', e)
      }
    }

    const handlePeerLeft = (peerId: string) => {
      closePeer(peerId)
    }

    // Attach listeners
    socket.on('peer-joined', handlePeerJoined)
    socket.on('signal', handleSignal)
    socket.on('peer-left', handlePeerLeft)

    // Notify backend that we are ready to stream
    socket.emit('ready-to-stream', { role })

    return () => {
      socket.off('peer-joined', handlePeerJoined)
      socket.off('signal', handleSignal)
      socket.off('peer-left', handlePeerLeft)

      // Close all active connections
      Object.keys(pcs.current).forEach((peerId) => {
        closePeer(peerId)
      })
    }
  }, [socket, localStream, role, addRemoteStream, removeRemoteStream])
}
