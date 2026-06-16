import asyncio
import cv2

# Importe o estado compartilhado da sua aplicação
from app.state import SharedState

# Importe a função vision_loop do arquivo onde você a definiu.
# Substitua 'seu_arquivo_visao' pelo nome do arquivo (sem o .py)
from app.tasks.vision_loop import vision_loop
async def main():
    print("Inicializando estado compartilhado...")
    state = SharedState()

    print("Iniciando tarefa de visão. Pressione Ctrl+C no terminal para encerrar.")
    
    try:
        # Cria e aguarda a execução da tarefa assíncrona
        vision_task = asyncio.create_task(vision_loop(state))
        await vision_task
        
    except asyncio.CancelledError:
        print("\nTarefa de visão cancelada com sucesso.")
    except Exception as e:
        print(f"\nErro fatal durante a execução: {e}")

if __name__ == "__main__":
    try:
        # Ponto de entrada do Asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        # Captura o Ctrl+C para encerrar o programa graciosamente
        print("\nPrograma encerrado pelo usuário (KeyboardInterrupt).")
    finally:
        # Garante que todas as janelas do OpenCV sejam fechadas (se você adicionar cv2.imshow depois)
        cv2.destroyAllWindows()