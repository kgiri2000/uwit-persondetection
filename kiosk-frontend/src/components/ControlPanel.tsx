import React from 'react'
import { useRoomStore } from '../store/useRoomStore'
import { Video, VideoOff, Mic, MicOff, LogOut, Camera } from 'lucide-react'

interface ControlPanelProps {
  onInitiateMedia: () => void
}

export const ControlPanel: React.FC<ControlPanelProps> = ({ onInitiateMedia }) => {
  const {
    localStream,
    videoEnabled,
    audioEnabled,
    toggleVideo,
    toggleAudio,
    resetStore,
    role,
  } = useRoomStore()

  const handleLeave = async () => {
    try {
      await fetch('/logout')
    } catch (e) {
      console.error('Failed to log out from server:', e)
    }
    resetStore()
  }

  if (role === 'observer') {
    return (
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-4 bg-black/85 border border-gray-800 px-6 py-3 rounded-full backdrop-blur-md shadow-2xl transition-all duration-300">
        <span className="text-sm font-semibold text-gray-400 px-2 select-none">
          Observer Mode (Viewing Only)
        </span>
        <button
          onClick={handleLeave}
          className="flex items-center justify-center p-3 bg-red-600 hover:bg-red-500 text-white rounded-full transition-all duration-200 cursor-pointer shadow-md"
          title="Leave Room"
        >
          <LogOut size={20} />
        </button>
      </div>
    )
  }

  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-4 bg-black/85 border border-gray-800 px-6 py-3 rounded-full backdrop-blur-md shadow-2xl transition-all duration-300">
      {!localStream ? (
        <button
          onClick={onInitiateMedia}
          className="flex items-center gap-2 px-5 py-2.5 bg-uw-gold hover:bg-uw-gold/90 text-black font-bold rounded-full transition-all duration-200 shadow-md cursor-pointer text-sm"
        >
          <Camera size={18} />
          <span>Start Kiosk Camera</span>
        </button>
      ) : (
        <>
          <button
            onClick={toggleVideo}
            className={`flex items-center justify-center p-3 rounded-full transition-all duration-200 cursor-pointer shadow-md ${
              videoEnabled
                ? 'bg-gray-800 hover:bg-gray-700 text-white'
                : 'bg-red-600 hover:bg-red-500 text-white'
            }`}
            title={videoEnabled ? 'Stop Video' : 'Start Video'}
          >
            {videoEnabled ? <Video size={20} /> : <VideoOff size={20} />}
          </button>

          <button
            onClick={toggleAudio}
            className={`flex items-center justify-center p-3 rounded-full transition-all duration-200 cursor-pointer shadow-md ${
              audioEnabled
                ? 'bg-gray-800 hover:bg-gray-700 text-white'
                : 'bg-red-600 hover:bg-red-500 text-white'
            }`}
            title={audioEnabled ? 'Mute Mic' : 'Unmute Mic'}
          >
            {audioEnabled ? <Mic size={20} /> : <MicOff size={20} />}
          </button>
        </>
      )}

      <button
        onClick={handleLeave}
        className="flex items-center justify-center p-3 bg-red-600 hover:bg-red-500 text-white rounded-full transition-all duration-200 cursor-pointer shadow-md"
        title="Leave Room"
      >
        <LogOut size={20} />
      </button>
    </div>
  )
}
