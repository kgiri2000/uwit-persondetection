import React, { useEffect, useRef } from 'react'

interface VideoPlayerProps {
  stream: MediaStream
  label: string
  muted?: boolean
  isLocal?: boolean
  aiStatus?: string
  videoRef?: React.RefObject<HTMLVideoElement | null>
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  stream,
  label,
  muted = false,
  isLocal = false,
  aiStatus,
  videoRef,
}) => {
  const localRef = useRef<HTMLVideoElement | null>(null)
  const activeRef = videoRef || localRef

  useEffect(() => {
    const videoElement = activeRef.current
    if (videoElement) {
      videoElement.srcObject = stream
    }
    return () => {
      if (videoElement) {
        videoElement.srcObject = null
      }
    }
  }, [stream, activeRef])

  // Determine AI status color classes
  const getAiStatusColor = (status: string) => {
    if (status.includes('Person Detected')) return 'text-red-500 font-bold animate-pulse'
    if (status.includes('Active')) return 'text-green-500'
    if (status.includes('Loading')) return 'text-uw-gold animate-pulse'
    if (status.includes('Paused')) return 'text-gray-400'
    return 'text-gray-500'
  }

  return (
    <div className="relative w-full h-full bg-uw-cardBg rounded-xl overflow-hidden border-2 border-gray-800 flex items-center justify-center shadow-lg transition-all duration-300">
      <video
        ref={activeRef}
        autoPlay
        playsInline
        muted={muted}
        className={`w-full h-full object-cover bg-black ${isLocal ? 'scale-x-[-1]' : ''}`}
      />
      <div className="absolute bottom-4 left-4 bg-black/80 backdrop-blur-md px-3 py-2 rounded-lg border-l-4 border-uw-gold flex flex-col gap-1 shadow-md z-10">
        <span className="text-sm font-semibold tracking-wide text-white uppercase">
          {label}
        </span>
        {aiStatus && (
          <span className={`text-xs ${getAiStatusColor(aiStatus)}`}>
            {aiStatus}
          </span>
        )}
      </div>
    </div>
  )
}
