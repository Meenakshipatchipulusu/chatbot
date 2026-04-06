import speech_recognition as sr
recognizer = sr.Recognizer()
with sr.Microphone() as source:
    print("Speak something...")
    audio = recognizer.listen(source)
try:
    text = recognizer.recognize_google(audio)
    print("You said:", text)
except:
    print("Sorry, could not recognize your speech")
# import speech_recognition as sr

# # Create a recognizer object
# r = sr.Recognizer()

# # Path to your audio file
# audio_file = "audio.wav"

# try:
#     # Load the audio file
#     with sr.AudioFile(audio_file) as source:
#         print("Processing audio file...")
#         audio_data = r.record(source)

#     # Convert speech to text using Google Web Speech API
#     text = r.recognize_google(audio_data)

#     print("\n✅ Transcribed Text:")
#     print(text)

# except sr.UnknownValueError:
#     print("❌ Speech Recognition could not understand the audio")

# except sr.RequestError as e:
#     print(f"❌ Could not request results; {e}")

# except FileNotFoundError:
#     print("❌ Audio file not found. Check the file name/path.")