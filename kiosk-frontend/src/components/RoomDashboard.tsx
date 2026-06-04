import React, { useRef } from 'react'
import { useSocket } from '../hooks/useSocket'
import { useWebRTC } from '../hooks/useWebRTC'
import { useKioskAI } from '../hooks/useKioskAI'
import { GuestShelf } from './GuestShelf'
import { HostStage } from './HostStage'
import { ControlPanel } from './ControlPanel'
import { useRoomStore } from '../store/useRoomStore'

export const RoomDashboard: React.FC = () => {
  // Connect to backend websocket signalling
  useSocket()

  // Manage WebRTC connections
  useWebRTC()

  // Reference for local host camera to process object detection
  const localVideoRef = useRef<HTMLVideoElement | null>(null)
  useKioskAI(localVideoRef)

  const { setLocalStream } = useRoomStore()

  const handleInitiateMedia = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      })
      setLocalStream(stream)
    } catch (err) {
      console.error('Hardware access denied:', err)
      alert('Please allow camera and microphone permissions to join the video session.')
    }
  }

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-uw-darkBg flex flex-col justify-between">
      {/* Absolute floating Top Bar for Guests */}
      <GuestShelf />

      {/* Main viewport for Host streams */}
      <div className="flex-1 w-full h-full flex items-center justify-center">
        <HostStage localVideoRef={localVideoRef} />
      </div>

      {/* Floating Bottom controls */}
      <ControlPanel onInitiateMedia={handleInitiateMedia} />
    </div>
  )
}
